from django.shortcuts import render

from django.http import JsonResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view
from ..tasks import add
@api_view(['GET', 'POST'])
def test(request):
    add.delay(1, 2)
    return JsonResponse({"message": "Test route is working fine!!"}, status=status.HTTP_200_OK)