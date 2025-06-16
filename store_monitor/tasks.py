# tasks.py
import os
import csv
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from .models import StoreReport, Store , StoreTimezone
import pytz
from .utils import calculate_uptime_last_hour, calculate_uptime_last_day, calculate_uptime_last_week

@shared_task
def generate_store_report_task(report_id, now_utc):
    report = StoreReport.objects.get(id=report_id)
    report.status = "running"
    report.save()

    try:
        filename = f"store_report_{report_id}.csv"
        full_path = os.path.join(settings.MEDIA_ROOT, 'reports', filename)

        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                'store_id',
                'uptime_last_hour(in minutes)',
                'uptime_last_day(in hours)',
                'uptime_last_week(in hours)',
                'downtime_last_hour(in minutes)',
                'downtime_last_day(in hours)',
                'downtime_last_week(in hours)',
            ])

            for store in Store.objects.all():

                tz_obj = StoreTimezone.objects.filter(store_id=store.id).first()
                tz_str = tz_obj.timezone_str if tz_obj else 'America/Chicago'
                local_tz = pytz.timezone(tz_str)
                uptime_last_hour = calculate_uptime_last_hour(store.id, now_utc, local_tz)
                uptime_last_day = calculate_uptime_last_day(store.id, now_utc, local_tz)
                uptime_last_week = calculate_uptime_last_week(store.id, now_utc, local_tz)

                writer.writerow([
                    store.id,
                    uptime_last_hour['uptime_last_hour'],
                    uptime_last_day['uptime_hours'],
                    uptime_last_week['uptime_hours'],
                    uptime_last_hour['downtime_last_hour'],
                    uptime_last_day['downtime_hours'],
                    uptime_last_week['downtime_hours'],
                ])

        report.report_file.name = f'reports/{filename}'
        report.status = "completed"
        report.save()

    except Exception as e:
        report.status = f"failed: {str(e)}"
        report.save()
        raise

@shared_task
def add(a,b):
    return a + b