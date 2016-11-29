from django.conf.urls import url
from rest_framework.urlpatterns import format_suffix_patterns
from juniperapi import views

urlpatterns = [
    url(r'^juniper/devicelist/$', views.juniper_devicelist),
    url(r'^juniper/showroute/$', views.juniper_showroute),
    url(r'^juniper/exportpolicy/$', views.juniper_exportpolicy),
    url(r'^juniper/cachingpolicy/$', views.juniper_cachingpolicy),
    url(r'^juniper/searchzonefromroute/$', views.juniper_searchzonefromroute),
    url(r'^juniper/searchpolicy/$', views.juniper_searchpolicy),
]

urlpatterns = format_suffix_patterns(urlpatterns)
