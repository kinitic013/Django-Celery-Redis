from django.urls import path
from .views import (test)

urlpatterns = [
    #Test
    path('',test.test, name='test_route')
]