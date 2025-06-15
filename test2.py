import os
import django
from datetime import datetime, timedelta, time, timezone
import pytz
import psycopg2
from collections import defaultdict
from django.db import connection as conn
import csv

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "loop_project.settings")
django.setup()
from store_monitor.models import StoreTimezone, StoreBusinessHour , Store

reference_monday = datetime(2000, 1, 3).date()

def get_business_hours(store_id, tz_str):
    local_tz = pytz.timezone(tz_str)
    business_hours = [(time(0, 0), time(23, 59)) for _ in range(7)]
    
    for hour in StoreBusinessHour.objects.filter(store_id=store_id):
        business_hours[hour.day_of_week] = (hour.start_time_local, hour.end_time_local)
    
    return business_hours, local_tz

def is_within_business_hours(dt_local, business_hours):
    day = dt_local.weekday()  # Monday=0, Sunday=6
    start, end = business_hours[day]
    current_time = dt_local.time()
    
    # print(f"\n[DEBUG] Checking business hours for {dt_local.strftime('%A %Y-%m-%d %H:%M:%S')}")
    # print(f"[DEBUG] Business hours on day {day}: start = {start}, end = {end}")
    # print(f"[DEBUG] Current local time: {current_time}")
    
    if start < end:
        within = start <= current_time <= end
    else:
        # Overnight shift (e.g. 10 PM to 6 AM)
        within = current_time >= start or current_time <= end

    # print(f"[DEBUG] Within business hours? {'Yes' if within else 'No'}")
    return within


def historical_avg_status(store_id, local_dt, start_time, end_time, cursor):
    """
    Estimate the status for a given weekday and time range by averaging past entries.
    Returns a float between 0 and 1 (probability of being active).
    """
    target_dow = (local_dt.weekday() + 1) % 7 
    local_dt_utc = local_dt.astimezone(timezone.utc)

    cursor.execute("""
        SELECT AVG(CASE WHEN status = 'active' THEN 1 ELSE 0 END)
        FROM store_monitor_storestatus
        WHERE store_id = %s
          AND EXTRACT(DOW FROM timestamp_utc AT TIME ZONE %s) = %s
          AND (timestamp_utc AT TIME ZONE %s)::time BETWEEN %s AND %s
          AND timestamp_utc < %s
        LIMIT 100;
    """, [
        store_id,
        str(local_dt.tzinfo),
        target_dow,
        str(local_dt.tzinfo),
        start_time,
        end_time,
        local_dt_utc
    ])
    
    result = cursor.fetchone()
    return float(result[0]) if result and result[0] is not None else 0.5

def get_max_possible_uptime(start_utc, end_utc, business_hours, local_tz):
    """
    Calculate maximum uptime in minutes between start_utc and end_utc
    considering the business hours in the local time zone.
    """
    # Convert to local time
    start_local = start_utc.astimezone(local_tz)
    end_local = end_utc.astimezone(local_tz)

    # Get business hours for that day
    weekday = start_local.weekday()
    business_start, business_end = business_hours[weekday]

    # Construct datetime objects for business start and end on same day
    business_start_dt = start_local.replace(hour=business_start.hour, minute=business_start.minute, second=0, microsecond=0)
    business_end_dt = start_local.replace(hour=business_end.hour, minute=business_end.minute, second=0, microsecond=0)

    if business_end <= business_start:
        if start_local.time() < business_end:
            business_start_dt -= timedelta(days=1)
        business_end_dt += timedelta(days=1)

    overlap_start = max(start_local, business_start_dt)
    overlap_end = min(end_local, business_end_dt)
    
    if overlap_start < overlap_end:
        delta = (overlap_end - overlap_start).total_seconds() / 60
        return delta
    return 0


def calculate_uptime_last_hour(store_id, now_utc):
    cursor = conn.cursor()
    

    tz_obj = StoreTimezone.objects.filter(store_id=store_id).first()
    tz_str = tz_obj.timezone_str if tz_obj else 'America/Chicago'
    business_hours, local_tz = get_business_hours(store_id, tz_str)
    
    # Convert UTC to local timezone
    now_local = now_utc.astimezone(local_tz)
    start_time_local = now_local - timedelta(hours=1)
    
    start_time_utc = start_time_local.astimezone(timezone.utc)
    now_utc_normalized = now_utc.astimezone(timezone.utc)

    cursor.execute("""
        SELECT *
        FROM store_monitor_storestatus
        WHERE store_id = %s
        AND timestamp_utc BETWEEN %s AND %s
        ORDER BY timestamp_utc;
    """, [store_id, start_time_utc, now_utc_normalized])
    
    rows = cursor.fetchall()
    total_possible_uptime = get_max_possible_uptime(start_time_utc,now_utc_normalized,business_hours,local_tz)
    if(len(rows) == 0):
        start_range = (start_time_local - timedelta(hours=1)).time()
        end_range = (start_time_local + timedelta(hours=1)).time()
        if start_range < end_range:
            prob = historical_avg_status(store_id, now_utc_normalized, start_range, end_range, cursor)
        else:
            # midnight: split into two queries and average
            prob1 = historical_avg_status(store_id, now_utc_normalized, start_range, time(23, 59, 59), cursor)
            prob2 = historical_avg_status(store_id, now_utc_normalized, time(0, 0, 0), end_range, cursor)
            prob = (prob1 + prob2) / 2
        uptime = prob * total_possible_uptime
        downtime = (1 - prob) * total_possible_uptime
        cursor.close()
        return {
            "uptime": uptime,
            "downtime": downtime,
            "timezone_used": tz_str,
            "query_period_utc": f"{start_time_utc} to {now_utc_normalized}",
            "query_period_local": f"{start_time_local} to {now_local}"
        }
    
    active_duration = 0
    inactive_duration = 0
    for row in rows:
        curr_datetime = row[0]
        curr_status =row[1]
        if(is_within_business_hours(curr_datetime.astimezone(local_tz), business_hours)):
            if(curr_status == 'active' ):
                active_duration += 1
            elif curr_status == 'inactive' :
                inactive_duration += 1
    
    total_up_time = active_duration / (active_duration + inactive_duration) * total_possible_uptime if (active_duration + inactive_duration) > 0 else 0
    total_down_time = inactive_duration / (active_duration + inactive_duration) * total_possible_uptime if (active_duration + inactive_duration) > 0 else 0
    cursor.close()
    return {
        "uptime": total_up_time,
        "downtime": total_down_time,
        "timezone_used": tz_str,
        "query_period_utc": f"{start_time_utc} to {now_utc_normalized}",
        "query_period_local": f"{start_time_local} to {now_local}"
    }
    

def get_store_timezone_info(store_id):
    """Helper function to get timezone information for a store"""
    tz_obj = StoreTimezone.objects.filter(store_id=store_id).first()
    tz_str = tz_obj.timezone_str if tz_obj else 'America/Chicago'
    local_tz = pytz.timezone(tz_str)
    return tz_str, local_tz

def calculate_uptime_last_day(store_id, now_utc):
    cursor = conn.cursor()
    
    tz_obj = StoreTimezone.objects.filter(store_id=store_id).first()
    tz_str = tz_obj.timezone_str if tz_obj else 'America/Chicago'
    business_hours, local_tz = get_business_hours(store_id, tz_str)
    
    # Convert UTC to local timezone
    now_local = now_utc.astimezone(local_tz)
    start_time_local = now_local - timedelta(days=1)

    # Convert back to UTC for database query (all DB timestamps are in UTC)
    start_time_utc = start_time_local.astimezone(timezone.utc)
    now_utc_normalized = now_utc.astimezone(timezone.utc)
    
    total_uptime_minutes = 0
    total_possible_minutes = 0

    # Iterate hour by hour
    current_local = start_time_local
    while current_local < now_local:
        next_local = current_local + timedelta(hours=1)

        # Check if current hour is within business hours
        if is_within_business_hours(current_local, business_hours):
            # Convert to UTC for querying DB
            start_utc = current_local.astimezone(timezone.utc)
            end_utc = next_local.astimezone(timezone.utc)
            
            result = calculate_uptime_last_hour(store_id,end_utc)

            # Add to accumulators (60 minutes max per hour)
            total_uptime_minutes += result['uptime']
            total_possible_minutes += result['uptime'] + result['downtime']

        current_local = next_local

    uptime_percent = (total_uptime_minutes / total_possible_minutes) * 100 if total_possible_minutes else 0

    return {
        "uptime": total_uptime_minutes//60,
        "downtime": total_possible_minutes//60 - total_uptime_minutes//60,
        "uptime_percent": uptime_percent,
        "total_possible_hours": total_possible_minutes//60,
    }

def calculate_uptime_last_week(store_id, now_utc):
    cursor = conn.cursor()
    
    tz_obj = StoreTimezone.objects.filter(store_id=store_id).first()
    tz_str = tz_obj.timezone_str if tz_obj else 'America/Chicago'
    business_hours, local_tz = get_business_hours(store_id, tz_str)
    
    # Convert UTC to local timezone
    now_local = now_utc.astimezone(local_tz)
    start_time_local = now_local - timedelta(days=7)

    total_uptime_minutes = 0
    total_possible_minutes = 0

    current_local = start_time_local
    while current_local < now_local:
        next_local = current_local + timedelta(hours=1)

        if is_within_business_hours(current_local, business_hours):
            end_utc = next_local.astimezone(timezone.utc)

            result = calculate_uptime_last_hour(store_id, end_utc)

            total_uptime_minutes += result['uptime']
            total_possible_minutes += result['uptime'] + result['downtime']

        current_local = next_local

    uptime_percent = (total_uptime_minutes / total_possible_minutes) * 100 if total_possible_minutes else 0

    return {
        "uptime": total_uptime_minutes // 60,
        "downtime": (total_possible_minutes - total_uptime_minutes) // 60,
        "uptime_percent": uptime_percent,
        "total_possible_hours": total_possible_minutes // 60,
    }

def generate_report_util(now_utc):
    all_stores = Store.objects.all()
    writer = csv.writer(open('store_uptime_report.csv', 'w', newline=''))
    writer.writerow(['store_id','uptime_last_hour(in minutes)', 'uptime_last_day(in hours)', 'uptime_last_week(in hours)', 'downtime_last_hour(in minutes)', 'downtime_last_day(in hours)', 'downtime_last_week(in hours)'])

    for store in all_stores:
        # Get the necessary data for each store
        uptime_last_hour = calculate_uptime_last_hour(store.id, now_utc)
        uptime_last_day = calculate_uptime_last_day(store.id, now_utc)
        uptime_last_week = calculate_uptime_last_week(store.id, now_utc)

        # Write the data to the CSV
        writer.writerow([
            store.id,
            uptime_last_hour['uptime'],
            uptime_last_day['uptime'],
            uptime_last_week['uptime'],
            uptime_last_hour['downtime'],
            uptime_last_day['downtime'],
            uptime_last_week['downtime'],
        ])

if __name__ == '__main__':
    # now = datetime(2024, 8, 1, 15, 45, 0, tzinfo=timezone.utc)
    now = datetime(2024, 10, 15, 5, 1, 9, tzinfo=timezone.utc)  # Example UTC time
    store_id = "baa17d5d-989f-4bdf-9ede-505bda85c671"
    
    print("=== Store Timezone Info ===")
    tz_str, local_tz = get_store_timezone_info(store_id)
    print(f"Store timezone: {tz_str}")
    print(f"Current time UTC: {now}")
    print(f"Current time Local: {now.astimezone(local_tz)}")
    
    print("\n=== Uptime Calculation ===")
    result = calculate_uptime_last_week(store_id, now)
    generate_report_util(now)
    print("\nResult:", result)