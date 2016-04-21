import os
import requests
import re

import json
import time

from flask import Flask, render_template, request, Response, jsonify
from flask.ext.sqlalchemy import SQLAlchemy

from bs4 import BeautifulSoup
from lxml import etree

from rq import Queue
from rq.job import Job
from worker import conn
from twilio.rest import TwilioRestClient


# initialize app, import environment variables, establish db, and setup queue
app = Flask(__name__)
app.config.from_object(os.environ['APP_SETTINGS'])
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
q = Queue(connection=conn)

# import all from models so we are able to interact with our database
from models import *

# this function deals with receiving multiple stocks in one text (ex. goog,aapl,yhoo)
def multiple_stocks(tickers, userid):
    job_ids=[]
    # receive a list of tickers and the userid associated to these tickers
    for ticker in tickers:
        # for each ticker in the list we will remove any non-alphabetical characters and convert to uppercase
        ticker = re.sub('[^a-zA-Z]+', '', ticker)
        ticker = ticker.upper()
        render_xml = True
        # here we send each ticker to a queue while being processed by our scrape_stocks function
        job = q.enqueue_call(
            func=scrape_stocks, args=(ticker, render_xml, userid,), result_ttl=5000
        )
        print(job.get_id())
        # since we are working with multiple tickers (thus generating multiple jobs) we will append each job id to a list (job_ids)
        job_ids.append(job.get_id())

    # once we have all of our job ids in our job_ids list, we pass this list and the associated user id to our send_multiple_texts function
    send_multiple_texts(job_ids, userid)
    # since Twilio is looking to receive an XML response from us, we generate and return a simple message that will be served once all our jobs are finished
    # Ideally this will be the last text message sent, but this is not always the case
    root = etree.Element('Response')
    child = etree.Element('Message')
    child.text = "Thanks for using TXTSTOCKS!"

    root.append(child)

    s = etree.tostring(root, pretty_print=True)
    return Response(s, mimetype='text/xml')

# this function takes care of creating and sending each text for each stock when multiple tickers are submitted at once
def send_multiple_texts(job_ids, userid):
    # here we loop through each of the job ids in our job_ids list
    for task in job_ids:
        job_key = task
        # this is our polling function to check and see if the current job we're looking at is finished
        # if the job is finished we send a text with the appropriate data
        # if the job is not finished we wait 1 second and check again
        def check_job(job_key):
            job = Job.fetch(job_key, connection=conn)
            if job.is_finished:
                result = Result.query.filter_by(id=job.result).first()
                results = sorted(
                    result.result.items()
                )
                # since the job is finished, we convert our results (list of tuples) to a dictionary to make referencing each item easier
                results = dict(results)

                # check if there was an error and set message to our errormsg
                # if there was no error, set our message to the appropriate stock data
                if "errormsg" in results:
                    print(results["errormsg"])
                    message = results["errormsg"]
                else:

                    message = results["company"] + '\n' + "Asking Price: " + results["ask"] + '\n' + "Change: " + results[
                        "change"] + '\n' + "Percent Change: " + results["percent_change"]

                    print(message)

                # pull in our Twilio auth data from config and connect to Twilio Rest Service
                ACCOUNT_SID = app.config['TWILIO_ACCOUNT_SID']
                AUTH_TOKEN = app.config['TWILIO_AUTH_TOKEN']

                client = TwilioRestClient(ACCOUNT_SID, AUTH_TOKEN)

                # use the userid that was passed along with this job and grab the associated phone number
                # finally send a text to that phone number with the message we declared above
                user = User.query.filter_by(id=userid).first()
                to = user.phone
                client.messages.create(
                    to=to,
                    from_="+14063185195",
                    body=message,
                )


            else:
                # if job is not finished, wait 1 second and check again
                time.sleep(1)
                check_job(job_key)
        # this checks each job the very first time
        check_job(job_key)
    return None

# this function takes care of the instances when a user texts "more info" to receive more info on the most recent stock they looked at
def more_info(userid):
    # here we generate an xml response
    root = etree.Element('Response')
    child = etree.Element('Message')
    # this is where we search our results table for the most recent value in the result column where userid is equal to our userid
    formatted_summary = Result.query.filter_by(userid=userid).order_by(Result.id.desc()).first()
    # then we must specify that we are only interested in grabbing the "formatted_quote_summary" data
    results = formatted_summary.result["formatted_quote_summary"]

    childtext = ""
    # for each key, value pair - append this info to our childtext string variable
    for key in results:
        s_key = str(key)
        s_val = str(results[key])

        childtext += s_key + " : " + s_val + "\n"
    #finally set child.text to the childtext string we just generated
    child.text = childtext


    root.append(child)

    s = etree.tostring(root, pretty_print=True)
    # return all our work as an xml response so Twilio will be happy
    return Response(s, mimetype='text/xml')

# this is our polling function for when a single stock ticker is texted
def wait_for_job(job_key):
    # grab the job by it's id and check to see if it is finished or not
    job = Job.fetch(job_key, connection=conn)
    # if the job is finished, get the data in the result column of our results table
    if job.is_finished:
        result = Result.query.filter_by(id=job.result).first()
        results = sorted(
            result.result.items()
        )

        # convert results (list of tuples) to dictionary to make referencing each item easier
        results = dict(results)

        # check if there is an error, if so construct xml that returns this error
        # if there is no error, format our xml response with the key, value data in our results dictionary.
        if "errormsg" in results:
            root = etree.Element('Response')
            child = etree.Element('Message')
            child.text = results["errormsg"]

            root.append(child)

            s = etree.tostring(root, pretty_print=True)
        else:
            root = etree.Element('Response')
            message = etree.Element('Message')

            root.append(message)
            body = etree.Element('Body')
            body.text = results["company"] + '\n' + "Asking Price: " + results["ask"] + '\n' + "Change: " + results[
                "change"] + '\n' + "Percent Change: " + results["percent_change"]

            message.append(body)

            # Twilio allows us to provide a Media element <Media> which allows us to take our scraped chart and return it as an MMS
            media = etree.Element('Media')

            media.text = results["media"]

            message.append(media)

            s = etree.tostring(root, pretty_print=True)

        return Response(s, mimetype='text/xml')
    else:
        # if the job isn't finished, wait 1 second and check again
        time.sleep(1)
        return wait_for_job(job_key)


def wait_for_xml(job_key):
    job = Job.fetch(job_key, connection=conn)
    if job.is_finished:
        result = Result.query.filter_by(id=job.result).first()
        results = sorted(
            result.result.items()
        )

        results = dict(results)

        if "errormsg" in results:
            root = etree.Element('Response')
            child = etree.Element('Message')
            child.text = results["errormsg"]

            root.append(child)

            s = etree.tostring(root, pretty_print=True)
        else:
            root = etree.Element('Response')
            message = etree.Element('Message')

            root.append(message)
            body = etree.Element('Body')
            body.text = results["company"] + '\n' + "Asking Price: " + results["ask"] + '\n' + "Change: " + results["change"] + '\n' + "Percent Change: " + results["percent_change"]

            message.append(body)

            media = etree.Element('Media')

            media.text = results["media"]

            message.append(media)

            s = etree.tostring(root, pretty_print=True)

        return Response(s, mimetype='text/xml')
    else:
        time.sleep(1)
        return wait_for_xml(job_key)

# this is our workhorse function... it does all the data scraping
def scrape_stocks(ticker, render_xml, userid):
    # if we are rendering xml, we know that we have received phone number and associated a userid to it, so we will assign these results to that userid
    # if we are not rendering xml, we know that this request is being served from a browser and there is not ownership of these results
    if render_xml:
        userid = userid
    else:
        userid = 0
    errors = []
    print("scraping")

    # our data source for all our stock info is Yahoo Finance, and we are able to return the correct stock page by constructing our url in this way
    base_url = 'http://finance.yahoo.com/q?d=t&s=' + ticker
    errormsg = ""

    # This is where we utilize the requests module to get the contents of our constructed url
    # Beautiful Soup (with the help of lxml) allows us to easily work with the raw html by offering functions that act like jquery selectors
    # we'll try to extract some basic info and if we run into any issues we will return an error
    try:
        rd = requests.get(base_url)
        html = rd.content.decode('utf-8', 'ignore')
        soup = BeautifulSoup(html, "lxml")
        error = soup.find_all(class_="error")
        suggest = soup.find_all(id="yfi_sym_lookup_results")
    except:
        errormsg = "Invalid Command."


        # try adding error to our results table in the db

        try:
            from models import Result

            result = Result(
                ticker=str(ticker),
                result={
                    "errormsg": errormsg

                },
                userid=userid
            )
            db.session.add(result)
            db.session.commit()
            return result.id
        except Exception as e:
            errors.append("Unable to add item to database.")
            return {"error": errors}

    # this section refers to error messages that our scraped from Yahoo Finance, not errors in our execution
    if error or suggest:
        if error:
            errormsg = error[0].h2.text
        if suggest:
            errormsg = "There are no results for the given search term."


        try:
            # once again we try to add our errors to the results table in our db
            from models import Result
            result = Result(
                ticker=str(ticker),
                result={
                    "errormsg": errormsg

                },
                userid=userid
            )
            db.session.add(result)
            db.session.commit()
            return result.id

        except Exception as e:
            errors.append("Unable to add item to database.")
            return {"error": errors}

    # if there were no errors (either in our execution or on Yahoo Finance's side) we can grab the stock data
    else:
        # here we use the unique css classes Yahoo Finance's page provides to specify where our data is at and we strip away any tags to return just the values we care about
        ask = soup.find_all(class_="time_rtq_ticker")[0].span.text.strip()
        # we must check whether the stock has gone up or down, because different css classes are applied in these two scenarios
        if soup.find_all(class_="up_g time_rtq_content"):
            change = soup.find_all(class_="up_g time_rtq_content")[0].span.contents[1].strip()
            percent_change = soup.find_all(class_="up_g time_rtq_content")[0].span.nextSibling.text.strip().replace("(",
                                                                                                                    "").replace(
                ")", "")

        if soup.find_all(class_="down_r time_rtq_content"):
            change = soup.find_all(class_="down_r time_rtq_content")[0].span.contents[1].strip()
            change = "-" + change
            percent_change = soup.find_all(class_="down_r time_rtq_content")[0].span.nextSibling.text.strip().replace(
                "(", "").replace(")", "")
            percent_change = "-" + percent_change

        company = soup.find_all(class_="title")[0].h2.text

        realticker = str(company).split("(")[1]
        realticker = realticker.split(")")[0]

        quote_summary = soup.find_all(class_="yfi_quote_summary")

        quote_summary1 = BeautifulSoup(str(quote_summary), "lxml")

        quote_summary2 = quote_summary1.find_all('tr')

        formatted_quote_summary = {}

        # finally after grabbing all the text data, we generate our stock chart's url
        chart = 'http://chart.finance.yahoo.com/t?s=' + realticker + '&lang=en-US&region=US&width=450&height=270'

        # this just strips the tags and makes our "formatted_quote_summary" data pretty and usable
        for i in quote_summary2:
            formatted_quote_summary[str(i.th.text)] = str(i.td.text)

    # no we can finally try to add our results to the results table in our db
    try:
        from models import Result
        result = Result(
            ticker=str(ticker),
            result={
                "ask": ask,
                "change": change,
                "percent_change": percent_change,
                "company": company,
                "media": chart,
                "formatted_quote_summary": formatted_quote_summary
            },
            userid=userid
        )
        db.session.add(result)
        db.session.commit()
        return result.id
    # in case of an error, we return an error
    except Exception as e:
        print(str(e))
        errors.append("Unable to add item to database.")
        return {"error": errors}


# this route allows a user to have the base stock scraping functionality from the web
@app.route('/')
def index():
    return render_template('index.html')


# this route is what we set our Twilio Messaging Request URL to
@app.route('/txt', methods=['GET', 'POST'])
def get_stocks():
    tickers = []
    # if Twilio is sending us get variables we grab our query from the Body variable and our phone number from the From variable
    if request.args.get('Body'):
        # if multiple tickers exist in our query, we create a list of tickers by splitting our query at the commas
        if request.args.get('Body').find(",") != -1:
            tickers = request.args.get('Body').split(",")


        phone = request.args.get('From')
        print(phone)
        errors=[]

        # here we try to add our phone number to our users table and receive a userid
        try:
            from models import User
            user = User(
                phone=phone
            )
            # print(db)
            db.session.add(user)
            db.session.commit()
            result = User.query.filter_by(phone=phone).first()
            userid = result.id
            print(userid)

        # or if there is an error, we return an error
        except Exception as e:
            print(str(e))
            errors.append("Unable to add item to database.")
            return {"error": errors}

        # if multiple tickers exist in our query, send this list of tickers and our userid to our multiple_stocks function for processing
        if tickers:
            return multiple_stocks(tickers, userid)

        # remove non-alphabetical characters from query and make sure we set our render_xml variable to True so we respond in a way that Twilio expects
        ticker = re.sub('[^a-zA-Z]+', '', request.args.get('Body'))
        render_xml = True
    # if we are not receiving this request from Twilio, then get our query from our input field in index.html and format our ticker for use in our scraping function
    else:
        data = json.loads(request.data.decode())
        ticker = data["Body"]
        ticker = re.sub('[^a-zA-Z]+', '', ticker)
        render_xml = False
        userid = 0


    ticker = ticker.upper()
    print(ticker)

    # in case render_xml is true and our query is for more info, send our userid to the more_info function
    if render_xml and ticker == "MOREINFO":
        return more_info(userid)

    # here we send our ticker, render_xml, and userid variables to a queue while being processed by our scrape_stocks function
    job = q.enqueue_call(
        func=scrape_stocks, args=(ticker, render_xml, userid,), result_ttl=5000
    )
    print(job.get_id())

    # if we are rendering xml, then send our job to wait_for_xml, else return our job id (so our javascript for index.html can utilize it)
    if render_xml:
        job_key = job.get_id()
        return wait_for_xml(job_key)
    else:
        return job.get_id()


# this route allows us to get the status for a job id and return a json representation of our result items if the job is finished
@app.route("/results/<job_key>", methods=['GET'])
def get_results(job_key):

    job = Job.fetch(job_key, connection=conn)

    if job.is_finished:
        result = Result.query.filter_by(id=job.result).first()
        results = sorted(
            result.result.items()
        )
        return jsonify(results)
    else:
        return "Not yet received!", 202

if __name__ == '__main__':
    app.run()