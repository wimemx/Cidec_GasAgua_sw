from celery import task
from celery.task.schedules import crontab
from celery.decorators import periodic_task

from c_center.models import ElectricDataTemp
from rbac.models import UserProfile
from django.contrib.auth.models import User
from tareas.models import test_tasks

from datetime import date

@task()
def run(person_id):
    print "Running determine_can_drink task for person %s" % person_id

    person = User.objects.get(pk=person_id)
    profile = UserProfile.objects.get(user=person)
    now = date.today()
    diff = now - profile.user_profile_birth_dates
    # i know, i know, this doesn't account for leap year
    age = diff.days / 365
    if age >= 21:
        test = test_tasks(task=person.username+" mayor de 21", value=str(age))
        test.save()
    else:
        test = test_tasks(task=person.username+" menor de 21", value=str(age))
        test.save()
    return age


@task()
def add():
    data=ElectricDataTemp.objects.all()
    max = -300000
    for dat in data:
        if dat.kWhIMPORT > max:
            max = dat.kWhIMPORT
    return max

@task(name="tasks.add2")
def add2(x,y):
    test = test_tasks(task="add2", value=str(x+y))
    test.save()
    return x + y

# this will run every minute, see http://celeryproject.org/docs/reference/celery.task.schedules.html#celery.task.schedules.crontab
@periodic_task(run_every=crontab(hour="*", minute="*", day_of_week="*"))
def test_one_minute():
    add.delay()
    print "firing test task"

# this will run every minute, see http://celeryproject.org/docs/reference/celery.task.schedules.html#celery.task.schedules.crontab
@periodic_task(run_every=crontab(hour="*", minute="*/2", day_of_week="*"))
def test_two_minute():
    print "firing another test"