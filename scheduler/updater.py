from apscheduler.schedulers.background import BackgroundScheduler
from .tasks import send_scheduled_messages

def start():
    scheduler = BackgroundScheduler()
    # Check every 30 seconds
    scheduler.add_job(send_scheduled_messages, 'interval', seconds=30)
    scheduler.start()
