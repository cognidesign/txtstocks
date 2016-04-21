import os
from apscheduler.schedulers.blocking import BlockingScheduler
from app import app

app.config.from_object(os.environ['APP_SETTINGS'])

sched = BlockingScheduler()

@sched.scheduled_job('interval', minutes=3)
def timed_job():
    from twilio.rest import TwilioRestClient

    # put your own credentials here
    ACCOUNT_SID = app.config['TWILIO_ACCOUNT_SID']
    AUTH_TOKEN = app.config['TWILIO_AUTH_TOKEN']

    client = TwilioRestClient(ACCOUNT_SID, AUTH_TOKEN)

    client.messages.create(
        to="14065987345",
        from_="+14063185195",
        body="Hey!",
    )

@sched.scheduled_job('cron', day_of_week='mon-fri', hour=17)
def scheduled_job():
    print('This job is run every weekday at 5pm.')

sched.start()