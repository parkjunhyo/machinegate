from django.shortcuts import render

# Create your views here.
from f5restapi.f5views.f5_devicelist import f5_devicelist 
from f5restapi.f5views.f5_virtualserverlist import f5_virtualserverlist
from f5restapi.f5views.f5_virtualserverlist_profile_clientside import f5_virtualserverlist_profile_clientside 
from f5restapi.f5views.f5_poolmemberlist import f5_poolmemberlist
from f5restapi.f5views.f5_poolmemberstatus import f5_poolmemberstatus
from f5restapi.f5views.f5_create_config_lb import f5_create_config_lb
from f5restapi.f5views.f5_stats_virtual import f5_stats_virtual
from f5restapi.f5views.f5_virtualserverstats import f5_virtualserverstats
from f5restapi.f5views.f5_virtualserverstats_by_rollback import f5_virtualserverstats_by_rollback 
from f5restapi.f5views.f5_virtualstats_top import f5_virtualstats_top 
from f5restapi.f5views.f5_snatranslation import f5_snatranslation

