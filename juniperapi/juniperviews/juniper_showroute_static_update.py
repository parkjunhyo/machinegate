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



def confirm_adding_static_route(_input_dict_value_, this_processor_queue, mongo_db_collection_name):
   #
   _hostName_ = str(_input_dict_value_[u'hostname'])
   #fromDB_clustering = exact_findout('juniperSrx_clusterGroup', {"clusterStatus" : "clustered", "hostname" : _hostName_})
   #_haHostName_ = str(fromDB_clustering[0][u'hahostname'])
   #
   _hostNameEvery_ = _find_clusteringMember_('juniperSrx_devicesInfomation', 'juniperSrx_clusterGroup', 'hostname', _hostName_)
   # 
   for _inputAddress_ in _input_dict_value_[u'routing_address']:
      _inputIPNetwork_ = IPNetwork(_inputAddress_)
      #for _hostName_string_ in [_hostName_, _haHostName_]:
      for _hostName_string_ in _hostNameEvery_:
         fromDB_routingTable = exact_findout(mongo_db_collection_name, {'hostname':_hostName_string_, 'update_method' : 'manual'})
         for _dictValue_ in fromDB_routingTable:
            _dbValueIPNetwork_ = IPNetwork(_dictValue_[u'routing_address'])
            if (_inputIPNetwork_ in _dbValueIPNetwork_) and (_dbValueIPNetwork_ in _inputIPNetwork_):
              return_object = {
                "items":[],
                "process_status":"error",
                "process_msg":"already static added"
              }
              this_processor_queue.put(return_object)
              return False
   #
   for _inputAddress_ in _input_dict_value_[u'routing_address']:
      _inputIPNetwork_ = IPNetwork(_inputAddress_)
      #for _hostName_string_ in [_hostName_, _haHostName_]:
      for _hostName_string_ in _hostNameEvery_:
         fromDB_routingTable = exact_findout(mongo_db_collection_name, {'hostname':_hostName_string_})
         for _dictValue_ in fromDB_routingTable:
            _dbValueIPNetwork_ = IPNetwork(_dictValue_[u'routing_address'])
            if (_inputIPNetwork_ in _dbValueIPNetwork_) or (_dbValueIPNetwork_ in _inputIPNetwork_):
              return_object = {
                "items":[],
                "process_status":"error",
                "process_msg":"%(_inputIPNetwork_)s is duplicated by %(_dbValueIPNetwork_)s of %(_hostName_string_)s" % {"_inputIPNetwork_":str(_inputIPNetwork_), "_dbValueIPNetwork_":str(_dbValueIPNetwork_), "_hostName_string_":str(_hostName_string_)}
              }
              this_processor_queue.put(return_object)
   #
   _updatingItems_ = []
   for _inputAddress_ in _input_dict_value_[u'routing_address']:
      #for _hostName_string_ in [_hostName_, _haHostName_]:
      for _hostName_string_ in _hostNameEvery_:
         _updatingItems_.append({"update_method" : "manual", "hostname" : str(_hostName_string_), "routing_address" : str(_inputAddress_), "zonename" : str(_input_dict_value_[u'zonename'])})
   # insert into the db 
   insert_dictvalues_list_into_mongodb(mongo_db_collection_name, _updatingItems_)
   # thread timeout 
   time.sleep(1)


@api_view(['POST','PUT','DELETE'])
@csrf_exempt
def juniper_showroute_static_update(request,format=None):

   mongo_db_collection_name = 'juniperSrx_routingTable'

   # get method
   #if request.method == 'GET':
   #  #return_result = {"items":obtainjson_from_mongodb(mongo_db_collection_name)}
   #  #return Response(json.dumps(return_result))
   #  return Response(json.dumps({}))

   if request.method == 'PUT':
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

           # queue generation
           processing_queues_list = []
           for _input_dict_value_ in _input_[u'items']:
              processing_queues_list.append(Queue(maxsize=0))
           # run processing to get information
           count = 0
           _processor_list_ = []
           for _input_dict_value_ in _input_[u'items']:
              this_processor_queue = processing_queues_list[count]
              _processor_ = Process(target = confirm_adding_static_route, args = (_input_dict_value_, this_processor_queue, mongo_db_collection_name,))
              _processor_.start()
              _processor_list_.append(_processor_)
              count = count + 1
           for _processor_ in _processor_list_:   
              _processor_.join()

           # get information from the queue
           search_result = []
           for _queue_ in processing_queues_list:
              while not _queue_.empty():
                       search_result.append(_queue_.get())
           #
           return Response(json.dumps(search_result))

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
         if ('items' in _input_.keys()) and (u'items' in _input_.keys()):
           #
           _dataAll_fromDB_ = []
           for _dictValue_ in _input_[u'items']:
              _fromDB_values_ = exact_findout('juniperSrx_routingTable', {"hostname":str(_dictValue_[u'hostname'])})           
              for _innerDict_ in _fromDB_values_:
                 if u'_id' in _innerDict_:
                   del _innerDict_[u'_id']
                 _dataAll_fromDB_.append(_innerDict_)
           #
           _zonesName_fromDB_ = []
           for _dictValue_ in _input_[u'items']:
              _fromDB_values_ = exact_findout('juniperSrx_devicesInfomation', {"hostname":str(_dictValue_[u'hostname'])})
              for _innerDict_ in _fromDB_values_:
                 if u'_id' in _innerDict_:
                   del _innerDict_[u'_id']
                 for _zoneName_ in [ _innerDict_[u'from_zone'], _innerDict_[u'to_zone'] ]:
                    _zoneNameString_ = str(_zoneName_)
                    if _zoneNameString_ not in _zonesName_fromDB_:
                      _zonesName_fromDB_.append(_zoneNameString_)
           #
           return_object = {
             "items":_dataAll_fromDB_,
             "zonesName":_zonesName_fromDB_,
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
           #
           #_haHostNames_ = []
           #for _dictValue_ in _input_[u'items']:
           #   _hostName_ = str(_dictValue_[u'hostname'])
           #   fromDB_clustering = exact_findout('juniperSrx_clusterGroup', {"clusterStatus" : "clustered", "hostname" : _hostName_})
           #   for _innerDict_ in fromDB_clustering:
           #      if str(_innerDict_[u'hahostname']) not in _haHostNames_:
           #        _haHostNames_.append(str(_innerDict_[u'hahostname']))
           ##
           #_hostNameAll_ = copy.copy(_haHostNames_)
           #for _dictValue_ in _input_[u'items']:
           #   _hostName_ = str(_dictValue_[u'hostname'])
           #   if _hostName_ not in _hostNameAll_:
           #     _hostNameAll_.append(_hostName_)
           #
           _hostNameAll_ = []
           for _dictValue_ in _input_[u'items']:
              _hostName_ = str(_dictValue_[u'hostname'])
              _tempHostNameEvery_ = _find_clusteringMember_('juniperSrx_devicesInfomation', 'juniperSrx_clusterGroup', 'hostname', _hostName_)
              for _tempValue_ in _tempHostNameEvery_:
                 if str(_tempValue_) not in _hostNameAll_:
                   _hostNameAll_.append(str(_tempValue_))
           #
           removing_items_list = []
           for _dictValue_ in _input_[u'items']:
              _tempBox_ = {}
              _tempBox_["zonename"] = str(_dictValue_[u'zonename'])
              _tempBox_["routing_address"] = str(_dictValue_[u'routing_address'])
              _tempBox_["update_method"] = "manual"
              for _hostName_ in _hostNameAll_:
                 _copied_tempBox_ = copy.copy(_tempBox_)
                 _copied_tempBox_["hostname"] = _hostName_
                 removing_items_list.append(_copied_tempBox_)

           # queue generation
           processing_queues_list = []
           for _input_dict_value_ in removing_items_list:
              processing_queues_list.append(Queue(maxsize=0))
           # run processing to get information
           count = 0
           _processor_list_ = []
           for _input_dict_value_ in removing_items_list:
              this_processor_queue = processing_queues_list[count]
              _processor_ = Process(target = remove_info_in_db, args = (_input_dict_value_, this_processor_queue, mongo_db_collection_name,))
              _processor_.start()
              _processor_list_.append(_processor_)
              count = count + 1
           for _processor_ in _processor_list_:
              _processor_.join()
           # get information from the queue
           search_result = []
           for _queue_ in processing_queues_list:
              while not _queue_.empty():
                   search_result.append(_queue_.get())
           #
           return Response(json.dumps(search_result))
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

