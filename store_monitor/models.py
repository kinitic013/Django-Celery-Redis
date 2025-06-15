import uuid
from django.db import models

class Store(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    def __str__(self):
        return f"Store {self.id}"


class StoreTimezone(models.Model):
    store = models.OneToOneField(Store, on_delete=models.CASCADE, related_name='timezone')
    timezone_str = models.CharField(max_length=100, default='America/Chicago')

    def __str__(self):
        return f"{self.store} - Timezone: {self.timezone_str}"


class StoreBusinessHour(models.Model):
    DAYS_OF_WEEK = [
        (0, "Monday"),
        (1, "Tuesday"),
        (2, "Wednesday"),
        (3, "Thursday"),
        (4, "Friday"),
        (5, "Saturday"),
        (6, "Sunday"),
    ]

    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='business_hours')
    day_of_week = models.IntegerField(choices=DAYS_OF_WEEK)
    start_time_local = models.TimeField()
    end_time_local = models.TimeField()

    class Meta:
        unique_together = ('store', 'day_of_week')

    def __str__(self):
        day = dict(self.DAYS_OF_WEEK).get(self.day_of_week, "Unknown")
        return f"{self.store} - {day}: {self.start_time_local} to {self.end_time_local}"


class StoreStatus(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='status_logs')
    timestamp_utc = models.DateTimeField()

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    status = models.TextField()

    class Meta:
        managed = False
        constraints = [
            models.UniqueConstraint(fields=['store', 'timestamp_utc'], name='store_timestamp_unique')
        ]
        indexes = [
            models.Index(fields=['store']),
            models.Index(fields=['timestamp_utc']),
        ]
        ordering = ['timestamp_utc']

    def __str__(self):
        return f"{self.store} - {self.status} at {self.timestamp_utc}"
    
    

class StoreReport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp_utc = models.DateTimeField(auto_now_add=True)
    report_file = models.FileField(upload_to='reports/', null=True, blank=True)
    status = models.CharField(max_length=100, default="pending")