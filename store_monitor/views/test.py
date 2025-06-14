from django.shortcuts import render

from django.http import JsonResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
# Create your views here.
@api_view(['GET', 'POST'])
def test(request):
    return JsonResponse({"message": "Test route is working fine!!"}, status=status.HTTP_200_OK)