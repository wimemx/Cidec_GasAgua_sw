from django.db import models
from c_center.models import ConsumerUnit

# Create your models here.
class DataStoreMonthlyGraphs(models.Model):
    consumer_unit = models.ForeignKey(ConsumerUnit,
                                      on_delete=models.PROTECT, null=True,
                                      blank=True)

    year = models.IntegerField()

    month = models. IntegerField()

    instant_data = models.TextField(null=True, blank=True)

    data_consumed = models.TextField(null=True, blank=True)

    statistics = models.TextField(null=True, blank=True)


