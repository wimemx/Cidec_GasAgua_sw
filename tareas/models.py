from django.db import models

class test_tasks(models.Model):
    task = models.CharField(max_length=200)
    executed_time = models.DateTimeField(auto_now=True)
    value = models.TextField()

    def __unicode__(self):
        return self.task + " - " + str(self.executed_time) + " - " + self.value