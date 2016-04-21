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

app = Flask(__name__)
app.config.from_object(os.environ['APP_SETTINGS'])
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

q = Queue(connection=conn)

from models import *

def multiple_stocks(tickers, userid):
    job_ids=[]
    for ticker in tickers:
        ticker = re.sub('[^a-zA-Z]+', '', ticker)
        ticker = ticker.upper()
        render_xml = True
        job = q.enqueue_call(
            func=scrape_stocks, args=(ticker, render_xml, userid,), result_ttl=5000
        )
        print(job.get_id())
        job_ids.append(job.get_id())


    send_multiple_texts(job_ids, userid)
    root = etree.Element('Response')
    child = etree.Element('Message')
    child.text = "Thanks for using TXTSTOCKS!"

    root.append(child)

    s = etree.tostring(root, pretty_print=True)
    return Response(s, mimetype='text/xml')


def send_multiple_texts(job_ids, userid):
    for task in job_ids:
        job_key = task

        def check_job(job_key):
            job = Job.fetch(job_key, connection=conn)
            if job.is_finished:
                result = Result.query.filter_by(id=job.result).first()
                results = sorted(
                    result.result.items()
                )
                # print(results)
                # print(type(results))
                # print(type(results[0]))
                results = dict(results)

                if "errormsg" in results:
                    print(results["errormsg"])
                else:

                    message = results["company"] + '\n' + "Asking Price: " + results["ask"] + '\n' + "Change: " + results[
                        "change"] + '\n' + "Percent Change: " + results["percent_change"]

                    print(message)

                ACCOUNT_SID = app.config['TWILIO_ACCOUNT_SID']
                AUTH_TOKEN = app.config['TWILIO_AUTH_TOKEN']

                client = TwilioRestClient(ACCOUNT_SID, AUTH_TOKEN)

                user = User.query.filter_by(id=userid).first()
                to = user.phone
                client.messages.create(
                    to=to,
                    from_="+14063185195",
                    body=message,
                )


            else:
                time.sleep(1)
                check_job(job_key)
        check_job(job_key)
    return None


def more_info(userid):
    root = etree.Element('Response')
    child = etree.Element('Message')
    formatted_summary = Result.query.filter_by(userid=userid).order_by(Result.id.desc()).first()
    # print(recent_ticker)
    results = formatted_summary.result["formatted_quote_summary"]
    # results = sorted(
    #     result.result.items()
    # )
    # results = dict(results)
    childtext = ""
    for key in results:
        s_key = str(key)
        s_val = str(results[key])

        childtext += s_key + " : " + s_val + "\n"
    child.text = childtext


    root.append(child)

    s = etree.tostring(root, pretty_print=True)
    return Response(s, mimetype='text/xml')


def wait_for_job(job_key):
    job = Job.fetch(job_key, connection=conn)
    if job.is_finished:
        result = Result.query.filter_by(id=job.result).first()
        results = sorted(
            result.result.items()
        )
        # print(results)
        # print(type(results))
        # print(type(results[0]))
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
            body.text = results["company"] + '\n' + "Asking Price: " + results["ask"] + '\n' + "Change: " + results[
                "change"] + '\n' + "Percent Change: " + results["percent_change"]

            message.append(body)

            media = etree.Element('Media')

            media.text = results["media"]

            message.append(media)

            s = etree.tostring(root, pretty_print=True)

        return Response(s, mimetype='text/xml')
    else:
        time.sleep(1)
        return wait_for_job(job_key)

def wait_for_xml(job_key):
    job = Job.fetch(job_key, connection=conn)
    if job.is_finished:
        result = Result.query.filter_by(id=job.result).first()
        results = sorted(
            result.result.items()
        )
        # print(results)
        # print(type(results))
        # print(type(results[0]))
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


def scrape_stocks(ticker, render_xml, userid):
    if render_xml:
        userid = userid
    else:
        userid = 0
    errors = []
    print("scraping")
    base_url = 'http://finance.yahoo.com/q?d=t&s=' + ticker
    errormsg = ""
    try:

        rd = requests.get(base_url)
        html = rd.content.decode('utf-8', 'ignore')
        soup = BeautifulSoup(html, "lxml")
        error = soup.find_all(class_="error")
        suggest = soup.find_all(id="yfi_sym_lookup_results")
    except:
        errormsg = "Invalid Command."


        # print(s)

        try:
            from models import Result

            result = Result(
                ticker=str(ticker),
                result={
                    "errormsg": errormsg

                },
                userid=userid
            )
            # print(db)
            db.session.add(result)
            db.session.commit()
            return result.id
        except Exception as e:
            # print(str(e))
            errors.append("Unable to add item to database.")
            return {"error": errors}

    if error or suggest:
        if error:
            errormsg = error[0].h2.text
        if suggest:
            errormsg = "There are no results for the given search term."


        try:
            from models import Result
            result = Result(
                ticker=str(ticker),
                result={
                    "errormsg": errormsg

                },
                userid=userid
            )
            # print(db)
            db.session.add(result)
            db.session.commit()
            return result.id
        except Exception as e:
            # print(str(e))
            errors.append("Unable to add item to database.")
            return {"error": errors}

    else:
        ask = soup.find_all(class_="time_rtq_ticker")[0].span.text.strip()
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

        chart = 'http://chart.finance.yahoo.com/t?s=' + realticker + '&lang=en-US&region=US&width=450&height=270'

        for i in quote_summary2:
            formatted_quote_summary[str(i.th.text)] = str(i.td.text)

        print(ask)
        print(change)
        print(percent_change)
        print(company)

        print(formatted_quote_summary)


        # print(s)
        print(chart)

        # data = {}
        # data['ticker'] = str(realticker)
        # data['ask'] = str(ask)
        # data['change'] = str(change)
        # data['percent_change'] = str(percent_change)
        # data['company'] = str(company)
        # data['media'] = str(chart)
        # data['formatted_quote_summary'] = formatted_quote_summary
        # data['xml'] = s
        # json_data = json.dumps(data)
        # raw_words = [w for w in text if nonPunct.match(w)]
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
        # print(db)
        db.session.add(result)
        db.session.commit()
        return result.id
    except Exception as e:
        print(str(e))
        errors.append("Unable to add item to database.")
        return {"error": errors}


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/txt', methods=['GET', 'POST'])
def get_stocks():
    tickers = []
    if request.args.get('Body'):
        if request.args.get('Body').find(",") != -1:
            tickers = request.args.get('Body').split(",")


        phone = request.args.get('From')
        print(phone)
        errors=[]

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
        except Exception as e:
            print(str(e))
            errors.append("Unable to add item to database.")
            return {"error": errors}

        if tickers:
            return multiple_stocks(tickers, userid)

        ticker = re.sub('[^a-zA-Z]+', '', request.args.get('Body'))
        render_xml = True
    else:
        data = json.loads(request.data.decode())
        ticker = data["Body"]
        ticker = re.sub('[^a-zA-Z]+', '', ticker)
        render_xml = False
        userid = 0


    ticker = ticker.upper()
    print(ticker)

    if render_xml and ticker == "MOREINFO":
        return more_info(userid)


    job = q.enqueue_call(
        func=scrape_stocks, args=(ticker, render_xml, userid,), result_ttl=5000
    )
    print(job.get_id())
    if render_xml:
        job_key = job.get_id()
        return wait_for_xml(job_key)
    else:
        return job.get_id()

    ### Temporary
    # errormsg = "Invalid Command."
    # root = etree.Element('Response')
    # child = etree.Element('Message')
    # child.text = errormsg
    #
    # root.append(child)
    #
    # s = etree.tostring(root, pretty_print=True)
    ###

    # return Response(s, mimetype='text/xml')


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