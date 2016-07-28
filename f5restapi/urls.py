from django.conf.urls import url
from rest_framework.urlpatterns import format_suffix_patterns
from f5restapi import views

urlpatterns = [
    url(r'^f5/devicelist/$', views.f5_devicelist),
    url(r'^f5/virtualserverlist/$', views.f5_virtualserverlist),
    url(r'^f5/poolmemberlist/$', views.f5_poolmemberlist),
    url(r'^f5/poolmemberlist/(?P<poolname>[0-9A-Za-z_.-]+)/$', views.f5_poolmemberstatus),
    url(r'^f5/create/config/lb/$', views.f5_create_config_lb),
    url(r'^f5/stats/virtual/$', views.f5_stats_virtual),
    url(r'^f5/stats/virtual/(?P<virtualservername>[0-9A-Za-z_.-]+)/$', views.f5_virtualserverstats),
]

urlpatterns = format_suffix_patterns(urlpatterns)
