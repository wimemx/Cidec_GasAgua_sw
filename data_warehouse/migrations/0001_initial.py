# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'FiveMinuteInstant'
        db.create_table('data_warehouse_fiveminuteinstant', (
            ('instant_datetime', self.gf('django.db.models.fields.DateTimeField')(primary_key=True)),
        ))
        db.send_create_signal('data_warehouse', ['FiveMinuteInstant'])

        # Adding model 'HourInstant'
        db.create_table('data_warehouse_hourinstant', (
            ('instant_datetime', self.gf('django.db.models.fields.DateTimeField')(primary_key=True)),
        ))
        db.send_create_signal('data_warehouse', ['HourInstant'])

        # Adding model 'DayInstant'
        db.create_table('data_warehouse_dayinstant', (
            ('instant_datetime', self.gf('django.db.models.fields.DateTimeField')(primary_key=True)),
        ))
        db.send_create_signal('data_warehouse', ['DayInstant'])

        # Adding model 'WeekInstant'
        db.create_table('data_warehouse_weekinstant', (
            ('instant_datetime', self.gf('django.db.models.fields.DateTimeField')(primary_key=True)),
        ))
        db.send_create_signal('data_warehouse', ['WeekInstant'])

        # Adding model 'ConsumerUnit'
        db.create_table('data_warehouse_consumerunit', (
            ('transactional_id', self.gf('django.db.models.fields.IntegerField')(primary_key=True)),
            ('building_name', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('part_of_building_name', self.gf('django.db.models.fields.CharField')(default=u'', max_length=128, null=True, blank=True)),
            ('electric_device_type_name', self.gf('django.db.models.fields.CharField')(max_length=128)),
        ))
        db.send_create_signal('data_warehouse', ['ConsumerUnit'])

        # Adding model 'ConsumerUnitFiveMinuteElectricData'
        db.create_table('data_warehouse_consumerunitfiveminuteelectricdata', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('consumer_unit', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['data_warehouse.ConsumerUnit'], on_delete=models.PROTECT)),
            ('instant', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['data_warehouse.FiveMinuteInstant'], on_delete=models.PROTECT)),
            ('kW', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=20, decimal_places=6, blank=True)),
            ('kvar', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=20, decimal_places=6, blank=True)),
            ('PF', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=20, decimal_places=6, blank=True)),
            ('kWhIMPORT', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=20, decimal_places=6, blank=True)),
            ('kvarhIMPORT', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=20, decimal_places=6, blank=True)),
        ))
        db.send_create_signal('data_warehouse', ['ConsumerUnitFiveMinuteElectricData'])

        # Adding unique constraint on 'ConsumerUnitFiveMinuteElectricData', fields ['consumer_unit', 'instant']
        db.create_unique('data_warehouse_consumerunitfiveminuteelectricdata', ['consumer_unit_id', 'instant_id'])

        # Adding model 'ConsumerUnitHourElectricData'
        db.create_table('data_warehouse_consumerunithourelectricdata', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('consumer_unit', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['data_warehouse.ConsumerUnit'], on_delete=models.PROTECT)),
            ('instant', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['data_warehouse.HourInstant'], on_delete=models.PROTECT)),
            ('kW', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=20, decimal_places=6, blank=True)),
            ('kvar', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=20, decimal_places=6, blank=True)),
            ('PF', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=20, decimal_places=6, blank=True)),
            ('kWhIMPORT', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=20, decimal_places=6, blank=True)),
            ('kvarhIMPORT', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=20, decimal_places=6, blank=True)),
        ))
        db.send_create_signal('data_warehouse', ['ConsumerUnitHourElectricData'])

        # Adding unique constraint on 'ConsumerUnitHourElectricData', fields ['consumer_unit', 'instant']
        db.create_unique('data_warehouse_consumerunithourelectricdata', ['consumer_unit_id', 'instant_id'])

        # Adding model 'ConsumerUnitDayElectricData'
        db.create_table('data_warehouse_consumerunitdayelectricdata', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('consumer_unit', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['data_warehouse.ConsumerUnit'], on_delete=models.PROTECT)),
            ('instant', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['data_warehouse.DayInstant'], on_delete=models.PROTECT)),
            ('kW', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=20, decimal_places=6, blank=True)),
            ('kvar', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=20, decimal_places=6, blank=True)),
            ('PF', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=20, decimal_places=6, blank=True)),
            ('kWhIMPORT', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=20, decimal_places=6, blank=True)),
            ('kvarhIMPORT', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=20, decimal_places=6, blank=True)),
        ))
        db.send_create_signal('data_warehouse', ['ConsumerUnitDayElectricData'])

        # Adding unique constraint on 'ConsumerUnitDayElectricData', fields ['consumer_unit', 'instant']
        db.create_unique('data_warehouse_consumerunitdayelectricdata', ['consumer_unit_id', 'instant_id'])

        # Adding model 'ConsumerUnitWeekElectricData'
        db.create_table('data_warehouse_consumerunitweekelectricdata', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('consumer_unit', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['data_warehouse.ConsumerUnit'], on_delete=models.PROTECT)),
            ('instant', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['data_warehouse.WeekInstant'], on_delete=models.PROTECT)),
            ('kW', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=20, decimal_places=6, blank=True)),
            ('kvar', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=20, decimal_places=6, blank=True)),
            ('PF', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=20, decimal_places=6, blank=True)),
            ('kWhIMPORT', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=20, decimal_places=6, blank=True)),
            ('kvarhIMPORT', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=20, decimal_places=6, blank=True)),
        ))
        db.send_create_signal('data_warehouse', ['ConsumerUnitWeekElectricData'])

        # Adding unique constraint on 'ConsumerUnitWeekElectricData', fields ['consumer_unit', 'instant']
        db.create_unique('data_warehouse_consumerunitweekelectricdata', ['consumer_unit_id', 'instant_id'])


    def backwards(self, orm):
        # Removing unique constraint on 'ConsumerUnitWeekElectricData', fields ['consumer_unit', 'instant']
        db.delete_unique('data_warehouse_consumerunitweekelectricdata', ['consumer_unit_id', 'instant_id'])

        # Removing unique constraint on 'ConsumerUnitDayElectricData', fields ['consumer_unit', 'instant']
        db.delete_unique('data_warehouse_consumerunitdayelectricdata', ['consumer_unit_id', 'instant_id'])

        # Removing unique constraint on 'ConsumerUnitHourElectricData', fields ['consumer_unit', 'instant']
        db.delete_unique('data_warehouse_consumerunithourelectricdata', ['consumer_unit_id', 'instant_id'])

        # Removing unique constraint on 'ConsumerUnitFiveMinuteElectricData', fields ['consumer_unit', 'instant']
        db.delete_unique('data_warehouse_consumerunitfiveminuteelectricdata', ['consumer_unit_id', 'instant_id'])

        # Deleting model 'FiveMinuteInstant'
        db.delete_table('data_warehouse_fiveminuteinstant')

        # Deleting model 'HourInstant'
        db.delete_table('data_warehouse_hourinstant')

        # Deleting model 'DayInstant'
        db.delete_table('data_warehouse_dayinstant')

        # Deleting model 'WeekInstant'
        db.delete_table('data_warehouse_weekinstant')

        # Deleting model 'ConsumerUnit'
        db.delete_table('data_warehouse_consumerunit')

        # Deleting model 'ConsumerUnitFiveMinuteElectricData'
        db.delete_table('data_warehouse_consumerunitfiveminuteelectricdata')

        # Deleting model 'ConsumerUnitHourElectricData'
        db.delete_table('data_warehouse_consumerunithourelectricdata')

        # Deleting model 'ConsumerUnitDayElectricData'
        db.delete_table('data_warehouse_consumerunitdayelectricdata')

        # Deleting model 'ConsumerUnitWeekElectricData'
        db.delete_table('data_warehouse_consumerunitweekelectricdata')


    models = {
        'data_warehouse.consumerunit': {
            'Meta': {'object_name': 'ConsumerUnit'},
            'building_name': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'electric_device_type_name': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'part_of_building_name': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '128', 'null': 'True', 'blank': 'True'}),
            'transactional_id': ('django.db.models.fields.IntegerField', [], {'primary_key': 'True'})
        },
        'data_warehouse.consumerunitdayelectricdata': {
            'Meta': {'unique_together': "(('consumer_unit', 'instant'),)", 'object_name': 'ConsumerUnitDayElectricData'},
            'PF': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '6', 'blank': 'True'}),
            'consumer_unit': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['data_warehouse.ConsumerUnit']", 'on_delete': 'models.PROTECT'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'instant': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['data_warehouse.DayInstant']", 'on_delete': 'models.PROTECT'}),
            'kW': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '6', 'blank': 'True'}),
            'kWhIMPORT': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '6', 'blank': 'True'}),
            'kvar': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '6', 'blank': 'True'}),
            'kvarhIMPORT': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '6', 'blank': 'True'})
        },
        'data_warehouse.consumerunitfiveminuteelectricdata': {
            'Meta': {'unique_together': "(('consumer_unit', 'instant'),)", 'object_name': 'ConsumerUnitFiveMinuteElectricData'},
            'PF': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '6', 'blank': 'True'}),
            'consumer_unit': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['data_warehouse.ConsumerUnit']", 'on_delete': 'models.PROTECT'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'instant': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['data_warehouse.FiveMinuteInstant']", 'on_delete': 'models.PROTECT'}),
            'kW': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '6', 'blank': 'True'}),
            'kWhIMPORT': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '6', 'blank': 'True'}),
            'kvar': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '6', 'blank': 'True'}),
            'kvarhIMPORT': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '6', 'blank': 'True'})
        },
        'data_warehouse.consumerunithourelectricdata': {
            'Meta': {'unique_together': "(('consumer_unit', 'instant'),)", 'object_name': 'ConsumerUnitHourElectricData'},
            'PF': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '6', 'blank': 'True'}),
            'consumer_unit': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['data_warehouse.ConsumerUnit']", 'on_delete': 'models.PROTECT'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'instant': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['data_warehouse.HourInstant']", 'on_delete': 'models.PROTECT'}),
            'kW': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '6', 'blank': 'True'}),
            'kWhIMPORT': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '6', 'blank': 'True'}),
            'kvar': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '6', 'blank': 'True'}),
            'kvarhIMPORT': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '6', 'blank': 'True'})
        },
        'data_warehouse.consumerunitweekelectricdata': {
            'Meta': {'unique_together': "(('consumer_unit', 'instant'),)", 'object_name': 'ConsumerUnitWeekElectricData'},
            'PF': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '6', 'blank': 'True'}),
            'consumer_unit': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['data_warehouse.ConsumerUnit']", 'on_delete': 'models.PROTECT'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'instant': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['data_warehouse.WeekInstant']", 'on_delete': 'models.PROTECT'}),
            'kW': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '6', 'blank': 'True'}),
            'kWhIMPORT': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '6', 'blank': 'True'}),
            'kvar': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '6', 'blank': 'True'}),
            'kvarhIMPORT': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '20', 'decimal_places': '6', 'blank': 'True'})
        },
        'data_warehouse.dayinstant': {
            'Meta': {'object_name': 'DayInstant'},
            'instant_datetime': ('django.db.models.fields.DateTimeField', [], {'primary_key': 'True'})
        },
        'data_warehouse.fiveminuteinstant': {
            'Meta': {'object_name': 'FiveMinuteInstant'},
            'instant_datetime': ('django.db.models.fields.DateTimeField', [], {'primary_key': 'True'})
        },
        'data_warehouse.hourinstant': {
            'Meta': {'object_name': 'HourInstant'},
            'instant_datetime': ('django.db.models.fields.DateTimeField', [], {'primary_key': 'True'})
        },
        'data_warehouse.weekinstant': {
            'Meta': {'object_name': 'WeekInstant'},
            'instant_datetime': ('django.db.models.fields.DateTimeField', [], {'primary_key': 'True'})
        }
    }

    complete_apps = ['data_warehouse']