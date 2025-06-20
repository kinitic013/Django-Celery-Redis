# Generated by Django 5.2.3 on 2025-06-12 08:24

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Store',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ],
        ),
        migrations.CreateModel(
            name='StoreTimezone',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timezone_str', models.CharField(default='America/Chicago', max_length=100)),
                ('store', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='timezone', to='store_monitor.store')),
            ],
        ),
        migrations.CreateModel(
            name='StoreBusinessHour',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('day_of_week', models.IntegerField(choices=[(0, 'Monday'), (1, 'Tuesday'), (2, 'Wednusday'), (3, 'Thusday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')])),
                ('start_time_local', models.TimeField()),
                ('end_time_local', models.TimeField()),
                ('store', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='business_hours', to='store_monitor.store')),
            ],
            options={
                'unique_together': {('store', 'day_of_week')},
            },
        ),
        migrations.CreateModel(
            name='StoreStatus',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp_utc', models.DateTimeField()),
                ('status', models.CharField(choices=[('active', 'Active'), ('inactive', 'Inactive')], max_length=10)),
                ('store', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='status_logs', to='store_monitor.store')),
            ],
            options={
                'ordering': ['timestamp_utc'],
                'indexes': [models.Index(fields=['store'], name='store_monit_store_i_68b46f_idx'), models.Index(fields=['timestamp_utc'], name='store_monit_timesta_03c6fb_idx')],
            },
        ),
    ]
