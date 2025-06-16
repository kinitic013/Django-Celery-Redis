# views.py
from rest_framework.decorators import api_view
from rest_framework.response import Response

from datetime import datetime
from ..models import StoreReport
from ..tasks import generate_store_report_task

@api_view(['POST'])
def trigger_report(request):
    timestamp_string = request.data.get('timestamp_utc')
    timestamp_utc = datetime.strptime(timestamp_string, "%Y-%m-%d %H:%M:%S")
    report = StoreReport.objects.create(status="pending", timestamp_utc=timestamp_utc)
    generate_store_report_task.delay(report_id = str(report.id), now_utc=timestamp_utc)  # Async background task
    return Response({
        "report_id": str(report.id),
        "status": "Report generation initiated"
    })
    
    
@api_view(['GET'])
def get_report(request, report_id):
    try:
        report = StoreReport.objects.get(id=report_id)
    except StoreReport.DoesNotExist:
        return Response({"error": "Report not found"}, status=404)

    if report.status != "completed":
        return Response({
            "status": report.status,
            "timestamp_utc": report.timestamp_utc
        })

    return Response({
        "status": report.status,
        "timestamp_utc": report.timestamp_utc,
        "report_file_url": request.build_absolute_uri(report.report_file.url)
    })
