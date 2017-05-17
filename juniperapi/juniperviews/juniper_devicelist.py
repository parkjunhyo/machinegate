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


class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders its content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)


def obtain_deviceinfo(dataDict_value, this_processor_queue, mongo_db_collection_name):
   #
   #
   dictBox = copy.copy(dataDict_value);
   #
   laststring_pattern = r"[ \t\n\r\f\v]+Interfaces:[ \t\n\r\f\v]+[ \t\n\r\f\va-zA-Z0-9\-\./_]+[ \t\n\r\f\v]+\{[a-zA-Z0-9]+:[a-zA-Z0-9]+\}[ \t\n\r\f\v]+"
   securityzone_information = runssh_clicommand(dictBox[u'apiaccessip'], laststring_pattern, "show security zones detail | no-more\n")
   
   _fromDB_for_hahostname_ = exact_findout('juniperSrx_clusterGroup', {"hostname":str(dictBox[u'hostname']), "clusterStatus" : "clustered"})
   
   if not len(_fromDB_for_hahostname_):
     return_object = {
       "items":[],
       "process_status":"error",
       "process_msg":"%(_hostname_)s does not have clustering" % {"_hostname_":str(dataDict_value[u'hostname'])}
     }
     this_processor_queue.put(return_object)
   else:
     #dictBox[u"hahostname"] = _fromDB_for_hahostname_[0][u"hahostname"]
     #
     stringcombination = str("".join(securityzone_information))
     pattern_search = "{(\w+):(\w+)}"
     searched_element = re.search(pattern_search, stringcombination, re.I)
     if searched_element:
       dictBox[u'failover'] = searched_element.group(1).strip()
     #
     count = 0
     zone_index_list = []
     interface_index_list = []
     for _string_ in securityzone_information:
        if re.search("^Security zone:", _string_, re.I):
          zone_index_list.append(count)
        if re.search("[ \t\n\r\f\v]+Interfaces:", _string_, re.I):
          interface_index_list.append(count)
        count = count + 1
     zone_index_count = len(zone_index_list)
     if (zone_index_list[-1] < len(securityzone_information)-1):
       zone_index_list.append(len(securityzone_information)-1)
     #
     _existed_zone_list_ = []
     for _index_ in range(zone_index_count):
        _zonename_ = (securityzone_information[zone_index_list[_index_]].strip().split()[-1])
        if not re.search(r"junos-host", _zonename_, re.I):
          if _zonename_ not in _existed_zone_list_:
            _existed_zone_list_.append(_zonename_)
     #
     _mongoInput_values_ = []
     for _fromzone_ in _existed_zone_list_:
        for _tozone_ in _existed_zone_list_:
           _fromzone_pattern_ = "^"+_fromzone_+"$"
           _tozone_pattern_ = "^"+_tozone_+"$"
           if (not re.match(_fromzone_pattern_, _tozone_)) or (not re.match(_tozone_pattern_, _fromzone_)):
             _this_dictBox_ = copy.copy(dictBox)
             _this_dictBox_[u'from_zone'] = _fromzone_
             _this_dictBox_[u'to_zone'] = _tozone_
             _this_dictBox_[u'zoneValidation'] = 'enable'
             _mongoInput_values_.append(_this_dictBox_)
     #
     insert_dictvalues_list_into_mongodb(mongo_db_collection_name, _mongoInput_values_)
     #
     return_object = {
         "items":[],
         "process_status":"done",
         "process_msg":"%(_hostname_)s informations are updated!" % {"_hostname_":str(dictBox[u'hostname'])}
     }
     this_processor_queue.put(return_object)

   # thread timeout 
   time.sleep(2)


def _updateChangeStatus_(dataDict_value, this_processor_queue, mongo_db_collection_name):
   #
   _insideDict_values_  = copy.copy(dataDict_value);
   #
   _thisFromZone_ = _insideDict_values_[u'from_zone']
   _thisToZone_ = _insideDict_values_[u'to_zone']
   _changeTo_status_ = _insideDict_values_[u'zoneValidationChange']
   _beforeStatus_ = _insideDict_values_[u'zoneValidation']
   _thisHostname_ = _insideDict_values_[u'hostname']
   #
   _fromDB_for_hahostname_ = exact_findout('juniperSrx_clusterGroup', {"hostname":str(_thisHostname_), "clusterStatus" : "clustered"})
   _thisHaHostname_ = _fromDB_for_hahostname_[0]['hahostname']
   #
   _hostnamesList_ = [str(_thisHostname_), str(_thisHaHostname_)]
   for _hostName_ in _hostnamesList_:
      _searchTarget_ = {"hostname":str(_hostName_), "from_zone":str(_thisFromZone_), "to_zone":str(_thisToZone_)}
      _fromDB_matched_ = exact_findout(mongo_db_collection_name, _searchTarget_)
      if len(_fromDB_matched_):
        remove_data_in_collection(mongo_db_collection_name, _searchTarget_)
        _thisMatched_values_ = _fromDB_matched_[0]
        _searchTarget_[u'zoneValidation'] = _changeTo_status_
        _searchTarget_[u'failover'] = _thisMatched_values_[u'failover']
        _searchTarget_[u'version'] = _thisMatched_values_ [u'version']
        _searchTarget_[u'location'] = _thisMatched_values_[u'location']
        _searchTarget_[u'model'] = _thisMatched_values_[u'model']
        _searchTarget_[u'apiaccessip'] = _thisMatched_values_[u'apiaccessip']
        insert_dictvalues_into_mongodb(mongo_db_collection_name, _searchTarget_)
   # 
   return_object = {
         "items":[],
         "process_status":"done",
         "process_msg":"%(_beforeStatus_) status change to %(_changeTo_status_)s" % {"_beforeStatus_":str(_beforeStatus_), "_changeTo_status_":str(_changeTo_status_)}
   }
   this_processor_queue.put(return_object)
   #
   time.sleep(2)


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

     #parameter_from = request.query_params.dict()
     #if u'devicehostname' not in parameter_from:
     #  return_result = {"items":obtainjson_from_mongodb(mongo_db_collection_name)}
     #  return Response(json.dumps(return_result))
     #else:
     #  parameter_hostname = parameter_from[u'devicehostname']
     #  _obtained_values_ = exact_findout(mongo_db_collection_name, {"devicehostname":str(parameter_hostname)})
     #  for _dictvalues_ in _obtained_values_:
     #     del _dictvalues_[u'_id']
     #  return Response(json.dumps({"items":_obtained_values_}))


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
          _fromDB_for_disable_ = exact_findout(mongo_db_collection_name, {"zoneValidation" : "disable"})
          #
          data_from_databasefile = obtainjson_from_mongodb('juniperSrx_registeredDevices')
          # queue generation
          processing_queues_list = []
          for dataDict_value in data_from_databasefile:
             processing_queues_list.append(Queue(maxsize=0))
 
          # remove collection
          remove_collection(mongo_db_collection_name)

          # run processing to get information
          count = 0
          _processor_list_ = []
          for dataDict_value in data_from_databasefile:
             this_processor_queue = processing_queues_list[count]
             _processor_ = Process(target = obtain_deviceinfo, args = (dataDict_value, this_processor_queue, mongo_db_collection_name))
             _processor_.start()
             _processor_list_.append(_processor_)
             count = count + 1
          for _processor_ in _processor_list_:
             _processor_.join()

          # get information from the queue
          search_result = []
          for _queue_ in processing_queues_list:
             while not _queue_.empty():
                  _get_values_ = _queue_.get()
                  search_result.append(_get_values_)
          # 
          if not len(search_result):
            remove_collection(mongo_db_collection_name)
            return_object = {
                "items":[],
                "process_status":"error",
                "process_msg":"all of registered devices information have been cleared"
            }
            return Response(json.dumps(return_object))
          #
          _disabled_recovery_ = []
          for _disabledDict_ in _fromDB_for_disable_:
             if u'_id' in _disabledDict_:
               del _disabledDict_[u'_id']
             remove_data_in_collection(mongo_db_collection_name, _disabledDict_)
             _disabled_recovery_.append(_disabledDict_)
          insert_dictvalues_list_into_mongodb(mongo_db_collection_name, _disabled_recovery_)
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
          _thisGet_value_ = copy.copy(_input_[u'items'])

          # queue generation
          processing_queues_list = []
          for dataDict_value in _thisGet_value_:
             processing_queues_list.append(Queue(maxsize=0))
          #
          count = 0
          _processor_list_ = []
          for dataDict_value in _thisGet_value_:
             this_processor_queue = processing_queues_list[count]
             _processor_ = Process(target = _updateChangeStatus_, args = (dataDict_value, this_processor_queue, mongo_db_collection_name,))
             _processor_.start()
             _processor_list_.append(_processor_)
             count = count + 1
          for _processor_ in _processor_list_:
             _processor_.join()
          
          # get information from the queue
          search_result = []
          for _queue_ in processing_queues_list:
             while not _queue_.empty():
                  _get_values_ = _queue_.get()
                  search_result.append(_get_values_)

          #return Response(json.dumps({"items":search_result}))
          return Response(json.dumps(search_result))

        # end of if auth_matched:
        else:
          return_object = {"items":[{"message":"no authorization!","process_status":"error"}]}
          return Response(json.dumps(return_object))
      # end of if re.search(r"system", system_property["role"], re.I):
      else:
        return_object = {"items":[{"message":"this host has no authorizaition!","process_status":"error"}]}
        return Response(json.dumps(return_object))

