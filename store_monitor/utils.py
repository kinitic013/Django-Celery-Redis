import os
import django
from datetime import datetime, timedelta, time, timezone
import pytz
import psycopg2
from collections import defaultdict
from django.db import connection as conn

from store_monitor.models import StoreTimezone, StoreBusinessHour , Store

reference_monday = datetime(2000, 1, 3).date()

reference_monday = datetime(2000, 1, 3).date()

def get_business_hours(store_id):
    business_hours = [(time(0, 0), time(23, 59)) for _ in range(7)]
    
    for hour in StoreBusinessHour.objects.filter(store_id=store_id):
        business_hours[hour.day_of_week] = (hour.start_time_local, hour.end_time_local)
    
    return business_hours

def is_within_business_hours(start_local, end_local, business_hours):
    day = start_local.weekday()

    for bh_start, bh_end in business_hours:
        bh_start_dt = datetime.combine(start_local.date(), bh_start, tzinfo=start_local.tzinfo)
        bh_end_dt = datetime.combine(start_local.date(), bh_end, tzinfo=start_local.tzinfo)

        # Handle overnight shift (e.g. 22:00 to 06:00 next day)
        if bh_end <= bh_start:
            bh_end_dt += timedelta(days=1)

        overlap_start = max(start_local, bh_start_dt)
        overlap_end = min(end_local, bh_end_dt)

        if overlap_start < overlap_end:
            overlap_minutes = (overlap_end - overlap_start).total_seconds() / 60
            return True, overlap_start.astimezone(pytz.utc), overlap_end.astimezone(pytz.utc), round(overlap_minutes)

    return False, None, None, 0

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


def calculate_uptime_last_hour(store_id, now_utc,local_tz):
    cursor = conn.cursor()
    
    business_hours = get_business_hours(store_id)
    end_time_local = now_utc.astimezone(local_tz)
    start_time_local = end_time_local - timedelta(hours=1)
    
    start_time_utc = start_time_local.astimezone(timezone.utc)
    end_time_utc = now_utc.astimezone(timezone.utc)

    cursor.execute("""
        SELECT *
        FROM store_monitor_storestatus
        WHERE store_id = %s
        AND timestamp_utc BETWEEN %s AND %s
        ORDER BY timestamp_utc;
    """, [store_id, start_time_utc, end_time_utc])

    rows = cursor.fetchall()
    total_possible_uptime = get_max_possible_uptime(start_time_utc,end_time_utc,business_hours,local_tz)
    if(len(rows) == 0):
        start_range = (start_time_local - timedelta(hours=1)).time()
        end_range = (start_time_local + timedelta(hours=1)).time()
        if start_range < end_range:
            prob = historical_avg_status(store_id, end_time_utc, start_range, end_range, cursor)
        else:
            # midnight: split into two queries and average
            prob1 = historical_avg_status(store_id, end_time_utc, start_range, time(23, 59, 59), cursor)
            prob2 = historical_avg_status(store_id, end_time_utc, time(0, 0, 0), end_range, cursor)
            prob = (prob1 + prob2) / 2
        uptime = prob * total_possible_uptime
        downtime = (1 - prob) * total_possible_uptime
        cursor.close()
        return {
            "uptime_last_hour": uptime,
            "downtime_last_hour": downtime,
            "query_period_utc": f"{start_time_utc} to {end_time_utc}",
            "query_period_local": f"{start_time_local} to {end_time_local}"
        }
    
    active_duration = 0
    inactive_duration = 0
    for row in rows:
        curr_datetime = row[0]
        curr_status =row[1]
        if(is_within_business_hours(curr_datetime.astimezone(local_tz),curr_datetime.astimezone(local_tz), business_hours)):
            if(curr_status == 'active' ):
                active_duration += 1
            elif curr_status == 'inactive' :
                inactive_duration += 1
    
    total_up_time = active_duration / (active_duration + inactive_duration) * total_possible_uptime if (active_duration + inactive_duration) > 0 else 0
    total_down_time = inactive_duration / (active_duration + inactive_duration) * total_possible_uptime if (active_duration + inactive_duration) > 0 else 0
    cursor.close()
    return {
        "uptime_last_hour": total_up_time,
        "downtime_last_hour": total_down_time,
        "query_period_utc": f"{start_time_utc} to {end_time_utc}",
        "query_period_local": f"{start_time_local} to {end_time_local}"
    }
    

def get_store_timezone_info(store_id):
    """Helper function to get timezone information for a store"""
    tz_obj = StoreTimezone.objects.filter(store_id=store_id).first()
    tz_str = tz_obj.timezone_str if tz_obj else 'America/Chicago'
    local_tz = pytz.timezone(tz_str)
    return tz_str, local_tz

def calculate_uptime_last_day(store_id, now_utc,local_tz):
    start_time_utc = now_utc - timedelta(days=1)
    end_time_utc = now_utc
    cursor = conn.cursor()
    
    business_hours = get_business_hours(store_id)
    # Convert UTC to local timezone
    end_time_local = end_time_utc.astimezone(local_tz)
    start_time_local = end_time_local - timedelta(days=7)

    total_uptime_minutes = 0
    total_possible_minutes = 0
    
    query = """
    WITH raw AS (
    SELECT
        time_bucket_gapfill(
        '2 hours', 
        timestamp_utc,
        start => %s,
        finish => %s
        ) AS two_hour_bucket,
        COUNT(CASE WHEN status = 'active' THEN 1 END) AS count_active,
        COUNT(CASE WHEN status = 'inactive' THEN 1 END) AS count_inactive
    FROM store_monitor_storestatus
    WHERE store_id = %s
        AND timestamp_utc BETWEEN %s AND %s
    GROUP BY two_hour_bucket
    )
    SELECT
    two_hour_bucket,
    COALESCE(locf(NULLIF(count_active, 0)), 0) AS count_active,
    COALESCE(locf(NULLIF(count_inactive, 0)), 0) AS count_inactive
    FROM raw
    ORDER BY two_hour_bucket;
    """

    cursor.execute(query, [start_time_utc, end_time_utc, store_id, start_time_utc, end_time_utc])
    current_interval_rows = cursor.fetchall()

    for row in current_interval_rows:
        two_hour_bucket, count_active, count_inactive = row
        hour_start_utc = two_hour_bucket
        hour_end_utc = two_hour_bucket + timedelta(hours=2) - timedelta(seconds=1)
            
        hour_start_local = hour_start_utc.astimezone(local_tz)
        hour_end_local = hour_end_utc.astimezone(local_tz)

        flag , start_bucket_utc, end_bucket_utc, overlap_minutes = is_within_business_hours(hour_start_local, hour_end_local, business_hours)
        if flag:
            # print(f"[DEBUG] Within business hours: {start_bucket_utc} to {end_bucket_utc}, overlap_minutes: {overlap_minutes}")
            total_possible_minutes += overlap_minutes
            if(count_active + count_inactive) > 0:
                total_uptime_minutes += (count_active)/(count_active + count_inactive) * overlap_minutes
            else:
                total_uptime_minutes += 0.5 * overlap_minutes # HERE INTERPOLATION BETTER LOGIC NEEDS TO BE ADDED
            
    cursor.close()
    uptime_percent = (total_uptime_minutes / total_possible_minutes) * 100 if total_possible_minutes else 0
    return {
        "uptime_hours": total_uptime_minutes // 60,
        "downtime_hours": (total_possible_minutes - total_uptime_minutes) // 60,
        "uptime_percent": uptime_percent,
        "total_possible_hours": total_possible_minutes // 60,
    }



def calculate_uptime_last_week(store_id, now_utc, local_tz):
    start_time_utc = now_utc - timedelta(days=7)
    end_time_utc = now_utc
    cursor = conn.cursor()

    business_hours = get_business_hours(store_id)

    # Convert UTC to local timezone
    end_time_local = now_utc.astimezone(local_tz)
    start_time_local = end_time_local - timedelta(days=7)

    total_uptime_minutes = 0
    total_possible_minutes = 0
    
    query = """
    WITH raw AS (
    SELECT
        time_bucket_gapfill(
        '2 hours', 
        timestamp_utc,
        start => %s,
        finish => %s
        ) AS two_hour_bucket,
        COUNT(CASE WHEN status = 'active' THEN 1 END) AS count_active,
        COUNT(CASE WHEN status = 'inactive' THEN 1 END) AS count_inactive
    FROM store_monitor_storestatus
    WHERE store_id = %s
        AND timestamp_utc BETWEEN %s AND %s
    GROUP BY two_hour_bucket
    )
    SELECT
    two_hour_bucket,
    COALESCE(locf(NULLIF(count_active, 0)), 0) AS count_active,
    COALESCE(locf(NULLIF(count_inactive, 0)), 0) AS count_inactive
    FROM raw
    ORDER BY two_hour_bucket;
    """

    cursor.execute(query, [start_time_utc, end_time_utc, store_id, start_time_utc, end_time_utc])
    current_interval_rows = cursor.fetchall()

    for row in current_interval_rows:
        two_hour_bucket, count_active, count_inactive = row
        hour_start_utc = two_hour_bucket
        hour_end_utc = two_hour_bucket + timedelta(hours=2) - timedelta(seconds=1)
            
        hour_start_local = hour_start_utc.astimezone(local_tz)
        hour_end_local = hour_end_utc.astimezone(local_tz)

        flag , start_bucket_utc, end_bucket_utc, overlap_minutes = is_within_business_hours(hour_start_local, hour_end_local, business_hours)
        if flag:
            # print(f"[DEBUG] Within business hours: {start_bucket_utc} to {end_bucket_utc}, overlap_minutes: {overlap_minutes}")
            total_possible_minutes += overlap_minutes
            if(count_active + count_inactive) > 0:
                total_uptime_minutes += (count_active)/(count_active + count_inactive) * overlap_minutes
            else:
                total_uptime_minutes += 0.5 * overlap_minutes # HERE INTERPOLATION BETTER LOGIC NEEDS TO BE ADDED
            
    cursor.close()
    uptime_percent = (total_uptime_minutes / total_possible_minutes) * 100 if total_possible_minutes else 0
    return {
        "uptime_hours": total_uptime_minutes // 60,
        "downtime_hours": (total_possible_minutes - total_uptime_minutes) // 60,
        "uptime_percent": uptime_percent,
        "total_possible_hours": total_possible_minutes // 60,
    }