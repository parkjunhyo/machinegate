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

from shared_function import runssh_clicommand as runssh_clicommand
from shared_function import start_end_parse_from_string as start_end_parse_from_string 
from shared_function import obtainjson_from_mongodb as obtainjson_from_mongodb 
from shared_function import findout_primary_devices as findout_primary_devices
from shared_function import search_items_matched_info_by_apiaccessip as search_items_matched_info_by_apiaccessip
from shared_function import info_iface_to_zonename as info_iface_to_zonename
from shared_function import update_dictvalues_into_mongodb as update_dictvalues_into_mongodb
from shared_function import remove_collection as remove_collection
from shared_function import exact_findout as exact_findout
from shared_function import insert_dictvalues_into_mongodb as insert_dictvalues_into_mongodb

class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders its content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)


def obtain_showroute(_primaryip_, device_information_values, this_processor_queue, mongo_db_collection_name):
   #
   reversed_sorted_iface_to_zone = info_iface_to_zonename(device_information_values)
   laststring_pattern =  r"via[ \t\n\r\f\v]+([a-zA-Z0-9\-\.\/\_\<\>\-\:\*\[\]]*)[ \t\n\r\f\v]+\{[a-zA-Z0-9]+:[a-zA-Z0-9]+\}[ \t\n\r\f\v]+"
   securityzone_information = runssh_clicommand(_primaryip_, laststring_pattern, "show route | no-more\n")
   #
   pattern_start = r"^([0-9]+.[0-9]+.[0-9]+.[0-9]+/[0-9]+)[ \t\n\r\f\v]*"
   pattern_end = "via[ \t\n\r\f\v]+([a-zA-Z0-9\.\/\_\<\>\-\:\*]*)$"
   start_end_linenumber_list = start_end_parse_from_string(securityzone_information, pattern_start, pattern_end)
   #
   _this_hostname_ = device_information_values[u'devicehostname']
   #
   for _start_end_index_list_ in start_end_linenumber_list:
      if len(_start_end_index_list_) == 2:
        searched_element = re.search(pattern_start, securityzone_information[_start_end_index_list_[0]])
        routing_net_value = searched_element.group(1).strip()        
        searched_element = re.search(pattern_end, securityzone_information[_start_end_index_list_[-1]])
        routing_nexthop_iface = searched_element.group(1).strip()
        #
        if not re.search('0.0.0.0/0', routing_net_value): 
        #
          if (str(routing_nexthop_iface) in reversed_sorted_iface_to_zone.keys()) or (unicode(routing_nexthop_iface) in reversed_sorted_iface_to_zone.keys()):
            routing_table_info = {}
            routing_table_info[u'devicehostname'] = _this_hostname_
            routing_table_info['apiaccessip'] = _primaryip_
            routing_table_info['routing_address'] = routing_net_value
            routing_table_info['zonename'] = reversed_sorted_iface_to_zone[routing_nexthop_iface]
            routing_table_info['update_method'] = 'auto'  
            # return the queue
            insert_dictvalues_into_mongodb(mongo_db_collection_name, routing_table_info)

   # thread timeout 
   done_msg = "%(_this_hostname_)s routing updated!" % {"_this_hostname_":_this_hostname_}
   this_processor_queue.put({"message":done_msg,"process_status":"done"})
   time.sleep(1)

@api_view(['GET','POST'])
@csrf_exempt
def juniper_showroute(request,format=None):

   mongo_db_collection_name = 'juniper_srx_routingtable'

   # get method
   if request.method == 'GET':
     parameter_from = request.query_params.dict()
     if u'devicehostname' not in parameter_from:
       #
       _devices_list_ = obtainjson_from_mongodb('juniper_srx_devices')
       _primaryip_list_ = findout_primary_devices(_devices_list_)
       #
       accessip_to_hostname_match = {}
       for _dictvalue_ in _devices_list_:
          accessip_to_hostname_match[_dictvalue_[u"apiaccessip"]] = _dictvalue_[u"devicehostname"]
       #
       hostname_list = []
       for _primaryip_ in _primaryip_list_:
          _searched_hostname_ = accessip_to_hostname_match[_primaryip_]
          if _searched_hostname_ not in hostname_list:
            hostname_list.append(_searched_hostname_)
       return_result = {"items":hostname_list}
       return Response(json.dumps(return_result))
     else:
       parameter_hostname = parameter_from[u'devicehostname']
       searched_values = exact_findout(mongo_db_collection_name, {"devicehostname":str(parameter_hostname)})
       for _dictvalue_ in searched_values:
          del _dictvalue_[u'_id']
       return_result = {"items":searched_values}
       return Response(json.dumps(return_result))
   

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

         device_information_values = obtainjson_from_mongodb('juniper_srx_devices')
         primary_devices = findout_primary_devices(device_information_values)

         ## manual static route search
         #renewed_static_routing = []
         #for _primaryip_ in primary_devices:
         #   manual_static_route = exact_findout(mongo_db_collection_name, {"apiaccessip":str(_primaryip_), "update_method":"manual"})
         #   for _dictvalue_ in manual_static_route:
         #      _temp_box_ = {}
         #      for _keyname_ in _dictvalue_:
         #         if _keyname_ != u'_id':
         #           _temp_box_[str(_keyname_)] = str(_dictvalue_[_keyname_])
         #      renewed_static_routing.append(_temp_box_)

         manual_static_route = exact_findout(mongo_db_collection_name, {"update_method":"manual"})
         for _dictvalue_ in manual_static_route:
            if u'_id' in _dictvalue_.keys():
              del _dictvalue_[u'_id']

         # remove collections
         remove_collection(mongo_db_collection_name)
        
         # queue generation
         processing_queues_list = []
         for _primaryip_ in primary_devices:
            processing_queues_list.append(Queue(maxsize=0))
         # run processing to get information
         count = 0
         _processor_list_ = []
         for _primaryip_ in primary_devices:
            matched_info = search_items_matched_info_by_apiaccessip(device_information_values, _primaryip_)
            this_processor_queue = processing_queues_list[count]
            _processor_ = Process(target = obtain_showroute, args = (_primaryip_, matched_info, this_processor_queue, mongo_db_collection_name))
            _processor_.start()
            _processor_list_.append(_processor_)
            # for next queue
            count = count + 1
         for _processor_ in _processor_list_:
            _processor_.join()

         # manual update 
         for _dictvalue_ in manual_static_route:
            insert_dictvalues_into_mongodb(mongo_db_collection_name, _dictvalue_)
         
         # get information from the queue
         search_result = []
         for _queue_ in processing_queues_list:
            while not _queue_.empty():
                 _get_values_ = _queue_.get()
                 search_result.append(_get_values_)

         if not len(search_result):
           remove_collection(mongo_db_collection_name)
           search_result = [{"message":"all of routing table cleared!", "process_status":"done"}]
         return Response(json.dumps({"items":search_result}))

       # end of if auth_matched:
       else:
         return_object = {"items":[{"message":"no authorization!","process_status":"error"}]}
         return Response(json.dumps(return_object))
     # end of if re.search(r"system", system_property["role"], re.I):
     else:
       return_object = {"items":[{"message":"this host has no authorizaition!","process_status":"error"}]}
       return Response(json.dumps(return_object))

