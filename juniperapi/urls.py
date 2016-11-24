from django.conf.urls import url
from rest_framework.urlpatterns import format_suffix_patterns
from juniperapi import views

urlpatterns = [
    url(r'^juniper/devicelist/$', views.juniper_devicelist),
    url(r'^juniper/showroute/$', views.juniper_showroute),
    url(r'^juniper/exportpolicy/$', views.juniper_exportpolicy),
    url(r'^juniper/cachingpolicy/$', views.juniper_cachingpolicy),
]

urlpatterns = format_suffix_patterns(urlpatterns)
