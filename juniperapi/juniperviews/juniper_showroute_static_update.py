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
from juniperapi.setting import system_property

import os,re,copy,json,time,threading,sys
import paramiko
from multiprocessing import Process, Queue, Lock
from netaddr import *

from shared_function import obtainjson_from_mongodb as obtainjson_from_mongodb 
from shared_function import exact_findout as exact_findout
from shared_function import insert_dictvalues_into_mongodb as insert_dictvalues_into_mongodb
from shared_function import insert_dictvalues_list_into_mongodb as insert_dictvalues_list_into_mongodb
from shared_function import remove_info_in_db as remove_info_in_db
from shared_function import remove_data_in_collection as remove_data_in_collection
from shared_function import _find_clusteringMember_ as _find_clusteringMember_

class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders its content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)


@api_view(['POST','DELETE'])
@csrf_exempt
def juniper_showroute_static_update(request,format=None):

   mongo_db_collection_name = 'juniperSrx_routingTable'

   if request.method == 'POST':
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
       # confirm auth
       if ('auth_key' not in _input_.keys()) and (u'auth_key' not in _input_.keys()):
         return_object = {
             "items":[],
             "process_status":"error",
             "process_msg":"no auth_password"
         }
         return Response(json.dumps(return_object))

       # 
       auth_matched = re.match(ENCAP_PASSWORD, _input_['auth_key'])
       if auth_matched:

         _dataForInsert_ = []
         for _dict_ in _input_[u'items']:
            _matchingDatabase_ = exact_findout('juniperSrx_registeredDevices', { u'hostname': _dict_[u'hostname'] })
            for _matcheDict_ in _matchingDatabase_:
               _apiaccessip_ = _matcheDict_[u'apiaccessip']
               _hostname_ = _matcheDict_[u'hostname']
               for _inDict_ in _dict_[u'routing_address']:
                  _staticMachingStatus_ = True
                  for _staticMatchedDict_ in exact_findout(mongo_db_collection_name, {u'apiaccessip': _apiaccessip_, u'hostname': _hostname_, u'update_method': u'static'}):
                     if (IPNetwork(_inDict_) in IPNetwork(_staticMatchedDict_[u'routing_address'])) and (IPNetwork(_staticMatchedDict_[u'routing_address']) in IPNetwork(_inDict_)):
                       _staticMachingStatus_ = False
                  if _staticMachingStatus_:
                    _insertingData_ = { 
                         u'apiaccessip': _matcheDict_[u'apiaccessip'], 
                         u'hostname': _matcheDict_[u'hostname'], 
                         u'update_method': u'static', 
                         u'routing_address': _inDict_, 
                         u'zonename': _dict_[u'zonename'] 
                    }
                    _dataForInsert_.append(_insertingData_)
         #
         if len(_dataForInsert_): 
           insert_dictvalues_list_into_mongodb(mongo_db_collection_name, _dataForInsert_)  
         #    
         return_object = {
               "items":[],
               "process_status":"done",
               "process_msg":"done"
         }
         return Response(json.dumps(return_object))
       # end of if auth_matched:
       else:
         return_object = {
             "items":[],
             "process_status":"error",
             "process_msg":"wrong auth_password"
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



   elif request.method == 'DELETE':
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
       # confirm auth
       if ('auth_key' not in _input_.keys()) and (u'auth_key' not in _input_.keys()):
         return_object = {
             "items":[],
             "process_status":"error",
             "process_msg":"no auth_password"
         }
         return Response(json.dumps(return_object))
       # 
       auth_matched = re.match(ENCAP_PASSWORD, _input_['auth_key'])
       if auth_matched:
         if ('items' in _input_.keys()) and (u'items' in _input_.keys()):
           for _dict_ in _input_[u'items']:
              remove_data_in_collection(mongo_db_collection_name, _dict_)
           #
           return_object = {
             "items":[],
             "process_status":"done",
             "process_msg":"done"
           }
           return Response(json.dumps(return_object))
         # end of if ('items' in _input_.keys()) and (u'items' in _input_.keys()):
         else:
           return_object = {
               "items":[],
               "process_status":"error",
               "process_msg":"no items in input"
           }
           return Response(json.dumps(return_object))
       # end of if auth_matched:
       else:
         return_object = {
             "items":[],
             "process_status":"error",
             "process_msg":"wrong auth_password"
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

