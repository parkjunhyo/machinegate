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
from juniperapi.setting import PARAMIKO_DEFAULT_TIMEWAIT
from juniperapi.setting import system_property 

import os,re,copy,json,time,threading,sys,random
import paramiko
from multiprocessing import Process, Queue, Lock


from shared_function import runssh_clicommand as runssh_clicommand
from shared_function import obtainjson_from_mongodb as obtainjson_from_mongodb 
from shared_function import remove_collection as remove_collection
from shared_function import insert_dictvalues_list_into_mongodb as insert_dictvalues_list_into_mongodb 
from shared_function import exact_findout as exact_findout
from shared_function import remove_data_in_collection as remove_data_in_collection
from shared_function import insert_dictvalues_into_mongodb as insert_dictvalues_into_mongodb
from shared_function import replace_dictvalues_into_mongodb as replace_dictvalues_into_mongodb


class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders its content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)


@api_view(['GET','POST', 'PUT'])
@csrf_exempt
def juniper_devicelist(request,format=None):

   mongo_db_collection_name = 'juniperSrx_devicesInfomation'

   if request.method == 'GET':
     return_object = {
         "items":obtainjson_from_mongodb(mongo_db_collection_name),
         "process_status":"done",
         "process_msg":"done"
     }
     return Response(json.dumps(return_object))


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
          #
          _zonedisabled_ = exact_findout(mongo_db_collection_name, {'zoneValidation':'disable'})
          #
          remove_collection(mongo_db_collection_name)
          # 
          _activeStatusMemoryByIP_ = {}
          _activeStatusMemoryByHostname_ = {}
          for _dict_ in obtainjson_from_mongodb('juniperSrx_hastatus'):
             if _dict_[u'apiaccessip'] not in _activeStatusMemoryByIP_.keys():
               _activeStatusMemoryByIP_[_dict_[u'apiaccessip']] = _dict_[u'failover']
             if _dict_[u'hostname'] not in _activeStatusMemoryByHostname_.keys():
               _activeStatusMemoryByHostname_[_dict_[u'hostname']] = _dict_[u'failover']
         
          #_clusterStatusMemory_ = {} 
          #for _dict_ in exact_findout('juniperSrx_clusterGroup', {"clusterStatus" : "clustered"}):
          #   if _dict_[u'hostname'] not in _clusterStatusMemory_.keys():
          #     _clusterStatusMemory_[_dict_[u'hostname']] = _dict_[u'hahostname']
          
          _zoneStatusMemoryByHostname_ = {}
          for _dict_ in obtainjson_from_mongodb('juniperSrx_zonestatus'):
             if _dict_[u'hostname'] not in _zoneStatusMemoryByHostname_.keys():
               _zoneStatusMemoryByHostname_[_dict_[u'hostname']] = []
             if re.match(str(_dict_[u'status']), 'on', re.I):
               if _dict_[u'zonename'] not in _zoneStatusMemoryByHostname_[_dict_[u'hostname']]:
                 _zoneStatusMemoryByHostname_[_dict_[u'hostname']].append(_dict_[u'zonename'])

          #
          _recreated_deviceinformation_ = []
          for _dict_ in obtainjson_from_mongodb('juniperSrx_registeredDevices'):
             copied_dict = copy.copy(_dict_)
             copied_keyname = copied_dict.keys()
             if u'_id' in copied_keyname:
               del copied_dict[u'_id']
             #
             copied_dict[u'failover'] = _activeStatusMemoryByHostname_[copied_dict[u'hostname']]
             #
             _validZoneName_ = []
             _thisHostName_ = copied_dict[u'hostname']
             if _thisHostName_ in _zoneStatusMemoryByHostname_.keys():
               _validZoneName_ = _zoneStatusMemoryByHostname_[_thisHostName_]
             #else:
             #  if _thisHostName_ in _clusterStatusMemory_.keys():
             #    _reverseHostName_ = _clusterStatusMemory_[_thisHostName_]
             #    if _reverseHostName_ in _zoneStatusMemoryByHostname_.keys():
             #      _validZoneName_ = _zoneStatusMemoryByHostname_[_reverseHostName_]
             #
             for from_zone in _validZoneName_:
                for to_zone in _validZoneName_:
                   #if not re.search(from_zone, to_zone) and not re.search(to_zone, from_zone): 
                   if not (re.search(from_zone, to_zone) and re.search(to_zone, from_zone)):
                      _outCreated_ = copy.copy(copied_dict)
                      _outCreated_[u'zoneValidation'] = unicode('enable')
                      _outCreated_[u'from_zone'] = from_zone
                      _outCreated_[u'to_zone'] = to_zone
                      _recreated_deviceinformation_.append(_outCreated_) 
                

          insert_dictvalues_list_into_mongodb(mongo_db_collection_name, _recreated_deviceinformation_)

          # recover disable
          for _dict_ in _zonedisabled_:
             _copied_ = copy.copy(_dict_)
             if u'_id' in _copied_:
               del _copied_[u'_id']
             if u'zoneValidation' in _copied_:
               del _copied_[u'zoneValidation']
             for _origin_ in  exact_findout(mongo_db_collection_name, _copied_):
                _copiedOrigin_ = copy.copy(_origin_)
                if u'_id' in _copiedOrigin_:
                  del _copiedOrigin_[u'_id']
                _changedOrign_ = copy.copy(_copiedOrigin_)
                _changedOrign_[u'zoneValidation'] = unicode('disable')
                replace_dictvalues_into_mongodb(mongo_db_collection_name, _copiedOrigin_, _changedOrign_)
          #
          search_result = {
              "items":[],
              "process_status":"done",
              "process_msg":"done"
          }
          #
          return Response(json.dumps(search_result))
          #return Response(json.dumps({"items":search_result}))

        # end of if auth_matched:
        else:
          return_object = {"items":[{"message":"no authorization!","process_status":"error"}]}
          return Response(json.dumps(return_object))
      # end of if re.search(r"system", system_property["role"], re.I):
      else:
        return_object = {"items":[{"message":"this host has no authorizaition!","process_status":"error"}]}
        return Response(json.dumps(return_object))
          

   elif request.method == 'PUT':
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
          #
          #_clusterStatusMemory_ = {}
          #for _dict_ in exact_findout('juniperSrx_clusterGroup', {"clusterStatus" : "clustered"}):
          #   if _dict_[u'hostname'] not in _clusterStatusMemory_.keys():
          #     _clusterStatusMemory_[_dict_[u'hostname']] = _dict_[u'hahostname']
          #
          _thisGet_value_ = copy.copy(_input_[u'items'])

          for _dict_ in _thisGet_value_:
             for _matcheddict_ in exact_findout(mongo_db_collection_name, _dict_):
                copied_matched = copy.copy(_matcheddict_)
                #
                if u'_id' in copied_matched:
                  del copied_matched[u'_id']
                change_dict = copy.copy(copied_matched)
                if re.match(str(change_dict[u'zoneValidation']), 'enable', re.I):
                  change_dict[u'zoneValidation'] = unicode('disable')
                else:
                  change_dict[u'zoneValidation'] = unicode('enable')
                #
                replace_dictvalues_into_mongodb(mongo_db_collection_name, copied_matched, change_dict)
                #
                #if copied_matched[u'hostname'] in _clusterStatusMemory_.keys():
                #  _clusterdeviceName_ = _clusterStatusMemory_[copied_matched[u'hostname']]
                #  for _reversematched_ in exact_findout(mongo_db_collection_name, {"hostname":_clusterdeviceName_, "from_zone":copied_matched[u'from_zone'], "to_zone":copied_matched[u'to_zone']}):
                #     reverseCopied = copy.copy(_reversematched_);
                #     if u'_id' in reverseCopied:
                #       del reverseCopied[u'_id']
                #     reverseChange = copy.copy(reverseCopied)
                #     if re.match(str(reverseChange[u'zoneValidation']), 'enable', re.I):
                #       reverseChange[u'zoneValidation'] = unicode('disable')
                #     else:
                #       reverseChange[u'zoneValidation'] = unicode('enable')
                #     #
                #     replace_dictvalues_into_mongodb(mongo_db_collection_name, reverseCopied, reverseChange)
                #  #
          search_result = {
              "items":[],
              "process_status":"done",
              "process_msg":"done"
          }
          return Response(json.dumps(search_result))

        # end of if auth_matched:
        else:
          return_object = {"items":[{"message":"no authorization!","process_status":"error"}]}
          return Response(json.dumps(return_object))
      # end of if re.search(r"system", system_property["role"], re.I):
      else:
        return_object = {"items":[{"message":"this host has no authorizaition!","process_status":"error"}]}
        return Response(json.dumps(return_object))

