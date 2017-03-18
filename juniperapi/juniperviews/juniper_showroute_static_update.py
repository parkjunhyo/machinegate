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
from juniperapi.setting import system_property

import os,re,copy,json,time,threading,sys
import paramiko
from multiprocessing import Process, Queue, Lock
from netaddr import *

from shared_function import obtainjson_from_mongodb as obtainjson_from_mongodb 
from shared_function import exact_findout as exact_findout
from shared_function import insert_dictvalues_into_mongodb as insert_dictvalues_into_mongodb
from shared_function import remove_info_in_db as remove_info_in_db
from shared_function import remove_data_in_collection as remove_data_in_collection

class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders its content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)

def confirm_adding_static_route(_input_dict_value_, this_processor_queue, mongo_db_collection_name, hostname_to_accessip_match):
   _devicehostname_ = str(_input_dict_value_[u'devicehostname'])
   _routing_address_ = str(_input_dict_value_[u'routing_address'])
   _zonenae_ = str(_input_dict_value_[u'zonename'])
   _done_items_ = {"apiaccessip":str(hostname_to_accessip_match[unicode(_devicehostname_)]), "devicehostname":str(_devicehostname_), "update_method":'manual', "routing_address":str(_routing_address_), "zonename":str(_zonenae_)}

   perfect_parameter = {"devicehostname":str(_devicehostname_), "routing_address":str(_routing_address_) , "zonename":str(_zonenae_)}
   perfect_matched = exact_findout(mongo_db_collection_name, perfect_parameter)
   if len(perfect_matched):
     _msg_ = "already routing infomation existed!"
     this_processor_queue.put({"message":_msg_,"process_status":"error"})
   else:
     partial_parameter = {"devicehostname":str(_devicehostname_), "routing_address":str(_routing_address_)}
     partial_matched = exact_findout(mongo_db_collection_name, partial_parameter)
     if len(partial_matched):
       _msg_ = "routing info duplicated! - other zone"
       this_processor_queue.put({"message":_msg_,"process_status":"done","process_done_items":_done_items_})
     else:
       _this_net_ = IPNetwork(_routing_address_)
       searched_values = exact_findout(mongo_db_collection_name, {"devicehostname":str(_devicehostname_)})
       duplicated_status = False
       for _dictvalue_ in searched_values:
          _from_net_ = IPNetwork(_dictvalue_["routing_address"])
          if (_this_net_ in _from_net_) or (_from_net_ in _this_net_):
            duplicated_status = True
            break
       if duplicated_status:
         _msg_ = "routing info duplicated! - network included!"
         this_processor_queue.put({"message":_msg_,"process_status":"done","process_done_items":_done_items_})
       else:
         _msg_ = "static routing updated!"
         this_processor_queue.put({"message":_msg_,"process_status":"done","process_done_items":_done_items_})
   # thread timeout 
   time.sleep(1)


@api_view(['GET','POST','DELETE'])
@csrf_exempt
def juniper_showroute_static_update(request,format=None):

   mongo_db_collection_name = 'juniper_srx_routingtable'

   # get method
   if request.method == 'GET':
     #return_result = {"items":obtainjson_from_mongodb(mongo_db_collection_name)}
     #return Response(json.dumps(return_result))
     return Response(json.dumps({}))

   elif request.method == 'POST':
     if re.search(r"system", system_property["role"], re.I):
       _input_ = JSONParser().parse(request)
       # confirm input type 
       if type(_input_) != type({}):
         return_object = {"items":[{"message":"input should be object or dictionary!!","process_status":"error"}]}
         return Response(json.dumps(return_object))
       # confirm auth
       if ('auth_key' not in _input_.keys()) and (u'auth_key' not in _input_.keys()):
         return_object = {"items":[{"message":"no authorization!","process_status":"error"}]}
         return Response(json.dumps(return_object))
       # 
       auth_matched = re.match(ENCAP_PASSWORD, _input_['auth_key'])
       if auth_matched:
         if ('items' in _input_.keys()) and (u'items' in _input_.keys()):
         # end of if ('items' in _input_.keys()) and (u'items' in _input_.keys()):
           # 
           hostname_to_accessip_match = {}
           for _dictvalue_ in obtainjson_from_mongodb('juniper_srx_devices'):
              hostname_to_accessip_match[_dictvalue_[u"devicehostname"]] = _dictvalue_[u"apiaccessip"]
           # queue generation
           processing_queues_list = []
           for _input_dict_value_ in _input_[u'items']:
              processing_queues_list.append(Queue(maxsize=0))
           # run processing to get information
           count = 0
           _processor_list_ = []
           for _input_dict_value_ in _input_[u'items']:
              this_processor_queue = processing_queues_list[count]
              _processor_ = Process(target = confirm_adding_static_route, args = (_input_dict_value_, this_processor_queue, mongo_db_collection_name, hostname_to_accessip_match,))
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
                   if re.search(str(_get_values_["process_status"]),"done",re.I) or re.search(str(_get_values_[u"process_status"]),"done",re.I):
                     insert_dictvalues_into_mongodb(mongo_db_collection_name, _get_values_["process_done_items"])
                   search_result.append(_get_values_)
           return Response(json.dumps({"items":search_result}))
         # end of if ('items' in _input_.keys()) and (u'items' in _input_.keys()):
         else:
           return_object = {"items":[{"message":"no items for request!","process_status":"error"}]}
           return Response(json.dumps(return_object))  
       # end of if auth_matched:
       else:
         return_object = {"items":[{"message":"no authorization!","process_status":"error"}]}
         return Response(json.dumps(return_object))
     # end of if re.search(r"system", system_property["role"], re.I):
     else:
       return_object = {"items":[{"message":"this host has no authorizaition!","process_status":"error"}]}
       return Response(json.dumps(return_object))


   elif request.method == 'DELETE':
     if re.search(r"system", system_property["role"], re.I):
       _input_ = JSONParser().parse(request)
       # confirm input type 
       if type(_input_) != type({}):
         return_object = {"items":[{"message":"input should be object or dictionary!!","process_status":"error"}]}
         return Response(json.dumps(return_object))
       # confirm auth
       if ('auth_key' not in _input_.keys()) and (u'auth_key' not in _input_.keys()):
         return_object = {"items":[{"message":"no authorization!","process_status":"error"}]}
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
                   _get_values_ = _queue_.get()
                   if re.search(str(_get_values_["process_status"]),"done",re.I) or re.search(str(_get_values_[u"process_status"]),"done",re.I):
                     remove_data_in_collection(mongo_db_collection_name, _get_values_["process_done_items"])
                   search_result.append(_get_values_)
           print search_result
           return Response(json.dumps({"items":search_result}))
         # end of if ('items' in _input_.keys()) and (u'items' in _input_.keys()):
         else:
           return_object = {"items":[{"message":"no items for request!","process_status":"error"}]}
           return Response(json.dumps(return_object))
       # end of if auth_matched:
       else:
         return_object = {"items":[{"message":"no authorization!","process_status":"error"}]}
         return Response(json.dumps(return_object))
     # end of if re.search(r"system", system_property["role"], re.I):
     else:
       return_object = {"items":[{"message":"this host has no authorizaition!","process_status":"error"}]}
       return Response(json.dumps(return_object))

