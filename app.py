import os
import requests
import re
from flask import Flask, render_template, request, Response
from flask.ext.sqlalchemy import SQLAlchemy

from bs4 import BeautifulSoup
from lxml import etree

app = Flask(__name__)
app.config.from_object(os.environ['APP_SETTINGS'])
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

from models import Result

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/txt')
def get_stocks():
    ticker = re.sub('[^a-zA-Z]+', '', request.args.get('Body'))
    ticker = ticker.upper()
    print(ticker)

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
        root = etree.Element('Response')
        child = etree.Element('Message')
        child.text = errormsg

        root.append(child)

        s = etree.tostring(root, pretty_print=True)

        print(s)

        return Response(s, mimetype='text/xml')


    if error or suggest:
        if error:
            errormsg = error[0].h2.text
        if suggest:
            errormsg = "There are no results for the given search term."
        root = etree.Element('Response')
        child = etree.Element('Message')
        child.text = errormsg

        root.append(child)

        s = etree.tostring(root, pretty_print=True)

        print(s)

    else:
        ask = soup.find_all(class_="time_rtq_ticker")[0].span.text.strip()
        if soup.find_all(class_="up_g time_rtq_content"):
            change = soup.find_all(class_="up_g time_rtq_content")[0].span.contents[1].strip()
            percent_change = soup.find_all(class_="up_g time_rtq_content")[0].span.nextSibling.text.strip().replace("(","").replace(")", "")

        if soup.find_all(class_="down_r time_rtq_content"):
            change = soup.find_all(class_="down_r time_rtq_content")[0].span.contents[1].strip()
            change = "-" + change
            percent_change = soup.find_all(class_="down_r time_rtq_content")[0].span.nextSibling.text.strip().replace("(","").replace(")", "")
            percent_change = "-" + percent_change

        company = soup.find_all(class_="title")[0].h2.text

        realticker = str(company).split("(")[1]
        realticker = realticker.split(")")[0]

        quote_summary = soup.find_all(class_="yfi_quote_summary")

        quote_summary1 = BeautifulSoup(str(quote_summary), "lxml")

        quote_summary2 = quote_summary1.find_all('tr')

        formatted_quote_summary = {}

        chart = 'http://chart.finance.yahoo.com/t?s='+realticker+'&lang=en-US&region=US&width=450&height=270'

        for i in quote_summary2:
            formatted_quote_summary[str(i.th.text)] = str(i.td.text)

        print(ask)
        print(change)
        print(percent_change)
        print(company)

        print(formatted_quote_summary)
        root = etree.Element('Response')
        message = etree.Element('Message')

        root.append(message)
        body = etree.Element('Body')
        body.text = ticker + '\n' + company + '\n' + "Asking Price: " + ask + '\n' + "Change: " + change + '\n' + "Percent Change: " + percent_change

        message.append(body)


        media = etree.Element('Media')

        media.text = chart

        message.append(media)

        s = etree.tostring(root, pretty_print=True)

        print(s)
        print(chart)

    return Response(s, mimetype='text/xml')



if __name__ == '__main__':
    app.run()