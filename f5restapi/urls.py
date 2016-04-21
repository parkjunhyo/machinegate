from django.conf.urls import url
from rest_framework.urlpatterns import format_suffix_patterns
from f5restapi import views

urlpatterns = [
    url(r'^f5/devicelist/', views.f5_devicelist),
]

urlpatterns = format_suffix_patterns(urlpatterns)
