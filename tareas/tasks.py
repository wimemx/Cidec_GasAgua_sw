from celery import task
from celery.task.schedules import crontab
from celery.decorators import periodic_task
from c_center.models import ElectricData

@task()
def add():
    data=ElectricData.objects.all()
    max = -300000
    for dat in data:
        if dat.kWhIMPORT > max:
            max = dat.kWhIMPORT
    return max

# this will run every minute, see http://celeryproject.org/docs/reference/celery.task.schedules.html#celery.task.schedules.crontab
@periodic_task(run_every=crontab(hour="*", minute="*", day_of_week="*"))
def test_one_minute():
    add.delay()
    print "firing test task"

# this will run every minute, see http://celeryproject.org/docs/reference/celery.task.schedules.html#celery.task.schedules.crontab
@periodic_task(run_every=crontab(hour="*", minute="*/2", day_of_week="*"))
def test_two_minute():
    print "firing another test"