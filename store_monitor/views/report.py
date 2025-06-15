# views.py
from rest_framework.decorators import api_view
from rest_framework.response import Response

from ..models import StoreReport
from ..tasks import generate_store_report_task

@api_view(['POST'])
def trigger_report(request):
    report = StoreReport.objects.create(status="pending")
    generate_store_report_task.delay(str(report.id))  # Async background task
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
