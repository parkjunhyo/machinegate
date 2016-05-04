from django.conf.urls import url
from rest_framework.urlpatterns import format_suffix_patterns
from f5restapi import views

urlpatterns = [
    url(r'^f5/devicelist/', views.f5_devicelist),
    url(r'^f5/virtualserverlist/', views.f5_virtualserverlist),
    url(r'^f5/poolmemberlist/', views.f5_poolmemberlist),
]

urlpatterns = format_suffix_patterns(urlpatterns)
