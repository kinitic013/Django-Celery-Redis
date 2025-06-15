from django.urls import path
from .views import (test , report)

urlpatterns = [
    #TEST ROUTE
    path('',test.test, name='test_route'),
    # STORE MONITOR REPORTS
    path('trigger_report', report.trigger_report, name='trigger_report'),
    path('get_report/<uuid:report_id>', report.get_report, name='get_report'),
]