from django.urls import path
from .views import (test_view, report_view)

urlpatterns = [
    #TEST ROUTE
    path('', test_view.test, name='test_route'),
    # STORE MONITOR REPORTS
    path('trigger_report', report_view.trigger_report, name='trigger_report'),
    path('get_report/<uuid:report_id>', report_view.get_report, name='get_report'),
]