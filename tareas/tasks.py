from celery import task
from celery.task.schedules import crontab
from celery.decorators import periodic_task

from data_warehouse.views import *

from datetime import date

@task(ignore_result=True)
def datawarehouse_run(
        fill_instants=None,
        fill_intervals=None,
        _update_consumer_units=None,
        populate_instant_facts=None,
        populate_interval_facts=None

):
    populate_data_warehouse(
        fill_instants,
        fill_intervals,
        _update_consumer_units,
        populate_instant_facts,
        populate_interval_facts
    )

@task(ignore_result=True)
def calculate_dw(granularity):
    data_warehouse_update(granularity)

# this will run every minute, see http://celeryproject.org/docs/reference/celery.task.schedules.html#celery.task.schedules.crontab
@periodic_task(run_every=crontab(minute='*/60'))
def data_warehouse_one_hour():
    #calculate_dw.delay("hour")
    data_warehouse_update("hour")
    print "firing periodic task - DW Hour, :)"

@periodic_task(run_every=crontab(minute=0, hour=0))
def data_warehouse_one_day():
    calculate_dw.delay("day")
    print "firing periodic task - DW Day"

@periodic_task(run_every=crontab(minute=0, hour=0, day_of_week='sun'))
def data_warehouse_one_week():
    calculate_dw.delay("week")
    print "firing periodic task - DW week"

# this will run every minute, see http://celeryproject.org/docs/reference/celery.task.schedules.html#celery.task.schedules.crontab
#@periodic_task(run_every=crontab(hour="*", minute="*/2", day_of_week="*"))
#def test_two_minute():
#    print "firing another test"