from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.renderers import JSONRenderer
from rest_framework.parsers import JSONParser

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils.six import BytesIO

#from juniperapi.setting import USER_DATABASES_DIR
from juniperapi.setting import USER_NAME
from juniperapi.setting import USER_PASSWORD
from juniperapi.setting import ENCAP_PASSWORD
from juniperapi.setting import RUNSERVER_PORT
from juniperapi.setting import PARAMIKO_DEFAULT_TIMEWAIT
#from juniperapi.setting import USER_VAR_CHCHES
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


@api_view(['GET','POST'])
@csrf_exempt
def juniper_showrulebyrequest(request,format=None):

   # get method
   if request.method == 'GET':
   
     _fromDB_values_ = exact_findout('juniperSrx_devicesInfomation', {"failover" : "primary","zoneValidation" : "enable"})
     _outValuseList_ = []
     for _dictValue_ in _fromDB_values_:
        _msgInput_ = {
           'hostname':_dictValue_[u'hostname'],
           'from_zone':_dictValue_[u'from_zone'],
           'to_zone':_dictValue_[u'to_zone']
        }
        _uniqueString_ = "%(hostname)s#%(from_zone)s#%(to_zone)s" % _msgInput_
        if _uniqueString_ not in _outValuseList_:
          _outValuseList_.append(_msgInput_)
     #   
     return_object = {
              "items":_outValuseList_,
              "process_status":"done",
              "process_msg":"done"
     }
     return Response(json.dumps(return_object))



   # post method
   elif request.method == 'POST':
     if re.search(r"system", system_property["role"], re.I):
       _input_ = JSONParser().parse(request)
       # confirm input type 
       if type(_input_) != type({}):
         return_object = {
              "items":[],
              "process_status":"error",
              "process_msg":"input wrong format"
         }
         return Response(json.dumps(return_object))

       # {u'items': [{u'to_zone': u'PCI', u'hostname': u'KRIS10-PUBF02-5400FW', u'from_zone': u'PRI'}]}
       # [{u'to_zone': u'PCI', u'hostname': u'KRIS10-PUBF02-5400FW', u'from_zone': u'PUB', u'option': u'no option'}]
       _outValuseList_ = []
       for _dictValue_ in _input_[u'items']:
          _copiedvalues_ = copy.copy(_dictValue_)
          if u'option' in _copiedvalues_:
            _optionString_ = str(_copiedvalues_[u'option']).strip()
            if re.search('deviceonly', _optionString_, re.I):
              del _copiedvalues_[u'from_zone']
              del _copiedvalues_[u'to_zone']
            del _copiedvalues_[u'option']
          #_fromDB_values_ = exact_findout('juniperSrx_cachePolicyTable', _dictValue_)
          _fromDB_values_ = exact_findout('juniperSrx_cachePolicyTable', _copiedvalues_)
          for _dict_ in _fromDB_values_:
             _copyiedDcit_ = copy.copy(_dict_)
             del _copyiedDcit_[u'_id']
             _outValuseList_.append(_copyiedDcit_)
       #  
       _sortingBox_ = {}
       for _dictValue_ in _outValuseList_:
          _hostNameKey_ = "%(hostname)s %(from_zone)s %(to_zone)s" % _dictValue_
          if _hostNameKey_ not in _sortingBox_.keys():
            _sortingBox_[_hostNameKey_] = {}
          _intIndex_ = int(_dictValue_[u'sequence_number'])
          if _intIndex_ not in _sortingBox_[_hostNameKey_].keys():
            _sortingBox_[_hostNameKey_][_intIndex_] = {}
          _sortingBox_[_hostNameKey_][_intIndex_] = _dictValue_
       #
       _outValuseList_ = []
       _hostGroup_ = _sortingBox_.keys()
       for hostZone in _hostGroup_:
          _indexNumber_ = _sortingBox_[hostZone].keys()
          _indexNumber_.sort()
          for _Number_ in _indexNumber_:
             _outValuseList_.append(_sortingBox_[hostZone][_Number_])
       #
       #_sortingBox_ = {} 
       #for _dictValue_ in _outValuseList_:
       #   _intIndex_ = int(_dictValue_[u'sequence_number'])
       #   if _intIndex_ not in _sortingBox_.keys():
       #     _sortingBox_[_intIndex_] = {}
       #   _sortingBox_[_intIndex_] = _dictValue_
       #
       #_indexNumber_ = _sortingBox_.keys()
       #_indexNumber_.sort()
       #
       #_outValuseList_ = []
       #for _Number_ in _indexNumber_:
       ##   _outValuseList_.append(_sortingBox_[_Number_])

       return_object = {
              "items":_outValuseList_,
              "process_status":"done",
              "process_msg":"done"
       }
       return Response(json.dumps(return_object))

     # end of if re.search(r"system", system_property["role"], re.I):
     else:
       return_object = {
              "items":[],
              "process_status":"error",
              "process_msg":"host is not system"
       }
       return Response(json.dumps(return_object))


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

