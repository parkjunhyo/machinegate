from django.shortcuts import render

# Create your views here.
from juniperapi.juniperviews.confirmauth import confirmauth
from juniperapi.juniperviews.juniper_devicelist import juniper_devicelist
from juniperapi.juniperviews.juniper_showroute import juniper_showroute
from juniperapi.juniperviews.juniper_exportpolicy import juniper_exportpolicy
from juniperapi.juniperviews.juniper_cachingpolicy import juniper_cachingpolicy
from juniperapi.juniperviews.juniper_cachingnat import juniper_cachingnat
from juniperapi.juniperviews.juniper_searchzonefromroute import juniper_searchzonefromroute
from juniperapi.juniperviews.juniper_searchpolicy import juniper_searchpolicy
from juniperapi.juniperviews.juniper_device_regi import juniper_device_regi
from juniperapi.juniperviews.juniper_showroute_static_update import juniper_showroute_static_update
from juniperapi.juniperviews.juniper_showrulebyrequest import juniper_showrulebyrequest
from juniperapi.juniperviews.juniper_clustering import juniper_clustering
