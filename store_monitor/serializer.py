from rest_framework import serializers
from .models import Store, StoreTimezone, StoreBusinessHour, StoreStatus , StoreReport


class StoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ['id']


class StoreTimezoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreTimezone
        fields = ['store', 'timezone_str']


class StoreBusinessHourSerializer(serializers.ModelSerializer):
    day_of_week_display = serializers.CharField(source='get_day_of_week_display', read_only=True)

    class Meta:
        model = StoreBusinessHour
        fields = ['store', 'day_of_week', 'day_of_week_display', 'start_time_local', 'end_time_local']


class StoreStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreStatus
        fields = ['store', 'timestamp_utc', 'status']

class StoreReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreReport
        fields = ['status', 'timestamp_utc', 'report_file']