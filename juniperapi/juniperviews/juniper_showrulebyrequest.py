from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.renderers import JSONRenderer
from rest_framework.parsers import JSONParser

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils.six import BytesIO

from juniperapi.setting import USER_DATABASES_DIR
from juniperapi.setting import USER_NAME
from juniperapi.setting import USER_PASSWORD
from juniperapi.setting import ENCAP_PASSWORD
from juniperapi.setting import RUNSERVER_PORT
from juniperapi.setting import PARAMIKO_DEFAULT_TIMEWAIT
from juniperapi.setting import USER_VAR_CHCHES
from juniperapi.setting import PYTHON_MULTI_PROCESS
from juniperapi.setting import PYTHON_MULTI_THREAD
from juniperapi.setting import system_property

import os,re,copy,json,time,threading,sys,random
import paramiko
from netaddr import *
from multiprocessing import Process, Queue, Lock

from shared_function import obtainjson_from_mongodb as obtainjson_from_mongodb
from shared_function import exact_findout as exact_findout


class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders its content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)


@api_view(['GET'])
@csrf_exempt
def juniper_showrulebyrequest(request,format=None):

   # get method
   if request.method == 'GET':
     parameter_from = request.query_params.dict()

     if u'to_zone' not in parameter_from:
       return_object = {"items":[{"message":"there is no proper values, to_zone!","process_status":"error"}]}
       return Response(json.dumps(return_object))
     if u'unique_name' not in parameter_from:
       return_object = {"items":[{"message":"there is no proper values, unique_name!","process_status":"error"}]}
       return Response(json.dumps(return_object))
     if u'devicehostname' not in parameter_from:
       return_object = {"items":[{"message":"there is no proper values, devicehostname!","process_status":"error"}]}
       return Response(json.dumps(return_object))
     if u'from_zone' not in parameter_from:
       return_object = {"items":[{"message":"there is no proper values, from_zone!","process_status":"error"}]}
       return Response(json.dumps(return_object))

     input_for_dbquery = {}
     input_for_dbquery['to_zone'] = str(parameter_from[u'to_zone'])
     input_for_dbquery['unique_name'] = str(parameter_from[u'unique_name'])
     input_for_dbquery['devicehostname'] = str(parameter_from[u'devicehostname'])
     input_for_dbquery['from_zone'] = str(parameter_from[u'from_zone'])

     _obtained_values_ = exact_findout('juniper_srx_rule_table_cache', input_for_dbquery)
     for _dictvalues_ in _obtained_values_:
        del _dictvalues_[u'_id']
     return Response(json.dumps({"items":_obtained_values_}))


######################################################################################
#        # input
#        _input_ = JSONParser().parse(request)
#
#        # cache directory
#        cache_filename = []
#        for _fname_ in os.listdir(USER_VAR_CHCHES):
#           if re.search("cachepolicy_", _fname_.strip(), re.I):
#             if _fname_ not in cache_filename:
#               cache_filename.append(_fname_)
#
#        # get devicelist
#        CURL_command = "curl http://0.0.0.0:"+RUNSERVER_PORT+"/juniper/devicelist/"
#        get_info = os.popen(CURL_command).read().strip()
#        stream = BytesIO(get_info)
#        _routing_dict_ = JSONParser().parse(stream)
#
#        CURL_command = "curl -H \"Accept: application/json\" -X POST -d \'"+json.dumps(_input_)+"\' http://0.0.0.0:"+RUNSERVER_PORT+"/juniper/searchzonefromroute/"
#        get_info = os.popen(CURL_command).read().strip()
#        stream = BytesIO(get_info)
#        data_from_CURL_command = JSONParser().parse(stream)
#######################################################################################

