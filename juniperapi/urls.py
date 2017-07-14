from django.conf.urls import url
from rest_framework.urlpatterns import format_suffix_patterns
from juniperapi import views

urlpatterns = [
    url(r'^juniper/confirmauth/$', views.confirmauth),
    url(r'^juniper/devicelist/$', views.juniper_devicelist),
    url(r'^juniper/devicelist/register/$', views.juniper_device_regi),
    url(r'^juniper/devicelist/hastatus/$', views.juniper_hastatusupdate),
    url(r'^juniper/devicelist/zonestatus/$', views.juniper_zonestatus),
    url(r'^juniper/devicelist/clustering/$', views.juniper_clustering),
    url(r'^juniper/showroute/$', views.juniper_showroute),
    url(r'^juniper/showroute/staticupdate/$', views.juniper_showroute_static_update),
    url(r'^juniper/showrulebyrequest/$', views.juniper_showrulebyrequest),
    url(r'^juniper/exportpolicy/$', views.juniper_exportpolicy),
    url(r'^juniper/cachingpolicy/$', views.juniper_cachingpolicy),
    url(r'^juniper/cachingnat/$', views.juniper_cachingnat),
    url(r'^juniper/searchzonefromroute/$', views.juniper_searchzonefromroute),
    url(r'^juniper/searchpolicy/$', views.juniper_searchpolicy),
]

urlpatterns = format_suffix_patterns(urlpatterns)
