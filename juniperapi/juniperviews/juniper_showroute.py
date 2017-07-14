from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.renderers import JSONRenderer
from rest_framework.parsers import JSONParser

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils.six import BytesIO

#from juniperapi.setting import USER_DATABASES_DIR
from juniperapi.setting import USER_VAR_ROUTING
from juniperapi.setting import USER_VAR_INTERFACES
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
from shared_function import sftp_file_download as sftp_file_download
from shared_function import start_end_parse_from_string as start_end_parse_from_string 
from shared_function import obtainjson_from_mongodb as obtainjson_from_mongodb 
from shared_function import findout_primary_devices as findout_primary_devices
from shared_function import search_items_matched_info_by_apiaccessip as search_items_matched_info_by_apiaccessip
from shared_function import info_iface_to_zonename as info_iface_to_zonename
from shared_function import update_dictvalues_into_mongodb as update_dictvalues_into_mongodb
from shared_function import remove_collection as remove_collection
from shared_function import exact_findout as exact_findout
from shared_function import insert_dictvalues_into_mongodb as insert_dictvalues_into_mongodb
from shared_function import insert_dictvalues_list_into_mongodb as insert_dictvalues_list_into_mongodb
from shared_function import _find_clusteringMember_ as _find_clusteringMember_


class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders its content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)


#def obtain_showroute(_primaryip_, this_processor_queue, mongo_db_collection_name):
def obtain_showroute(_primaryip_, mongo_db_collection_name):
   #
   HostNamesList = exact_findout('juniperSrx_registeredDevices',{ "apiaccessip" : str(_primaryip_) })
   _thisHostName_ = HostNamesList[0][u'hostname']
   #
   _ifName_memory_ = {}
   for _dict_ in exact_findout('juniperSrx_zonestatus',{ "status" : "on", "apiaccessip" : str(_primaryip_) }):
      _ifName_ = str(_dict_[u'interface'])
      if _ifName_ not in _ifName_memory_.keys():
        _ifName_memory_[_ifName_] = str(_dict_[u'zonename'])

   # routing
   _origin_filepath_ = "/var/tmp/thisHost_routingTableAll"
   _cmd_ = "show route | no-more | save %(_origin_filepath_)s\n" % {"_origin_filepath_":_origin_filepath_}
   laststring_pattern = "Wrote [0-9]* line[s]* of output to \'%(_origin_filepath_)s\'[ \t\n\r\f\v]+\{[a-zA-Z0-9]+:[a-zA-Z0-9]+\}[ \t\n\r\f\v]+" % {"_origin_filepath_":_origin_filepath_}
   runssh_clicommand(_primaryip_, laststring_pattern, _cmd_)
   _remote_filename_ = USER_VAR_ROUTING + "routingtable@%(_primaryip_)s" % {"_primaryip_":_primaryip_}
   sftp_file_download(_primaryip_, _origin_filepath_, _remote_filename_)
   #
   f = open(_remote_filename_, 'r')
   contents = f.readlines()
   f.close()
   #
   _addressIndex_ = []
   _count_ = 0
   for _line_ in contents:
      _lineNoSpace_ = str(_line_).strip()
      ipAddressPattern = "([0-9]+)\.[0-9]+\.[0-9]+\.[0-9]+\/[0-9]+"
      _searchStatus_ = re.search(ipAddressPattern, _lineNoSpace_)
      if _searchStatus_: 
      #if re.search("[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+\/[0-9]+", _lineNoSpace_):
        _fristNumber_ = int(_searchStatus_.group(1))
        if not (_fristNumber_ == int(0) and re.search("0\.0\.0\.0", _lineNoSpace_)):
        #if not re.search("^0\.0\.0\.0$", _lineNoSpace_):
          _addressIndex_.append(_count_)
      _count_ = _count_ + 1
   #
   routingMem = {}
   for _index_ in _addressIndex_:
      _firstLine_ = contents[_index_]
      _secondLine_ = contents[_index_ + 1]
      _addressKey_ = str(_firstLine_).strip().split()[0]
      _nextHopValue_ = str(_secondLine_).strip().split()[-1]
      #
      if _addressKey_ not in routingMem.keys():
        if _nextHopValue_ in _ifName_memory_.keys():
          routingMem[_addressKey_] = _ifName_memory_[_nextHopValue_]

   # save into database 
   _inputDataforDB_ = []
   routingMemKeyList = routingMem.keys()
   for _routingKey_ in routingMemKeyList:
      _inputBox_ = {}
      _inputBox_[u'apiaccessip'] = _primaryip_
      _inputBox_[u'hostname'] = _thisHostName_
      _inputBox_['routing_address'] = _routingKey_
      _inputBox_['zonename'] = routingMem[_routingKey_]
      _inputBox_['update_method'] = 'auto'
      _inputDataforDB_.append(_inputBox_)

   #for _hostName_ in _hostNameEvery_:
   #   routingMemKeyList = routingMem.keys()
   #   for _routingKey_ in routingMemKeyList:
   #      _inputBox_ = {}
   #      _inputBox_['hostname'] = _hostName_
   #      _inputBox_['routing_address'] = _routingKey_
   #      _inputBox_['zonename'] = routingMem[_routingKey_]
   #      _inputBox_['update_method'] = 'auto'
   #      _inputDataforDB_.append(_inputBox_)

   insert_dictvalues_list_into_mongodb(mongo_db_collection_name, _inputDataforDB_)
   #
   #return_object = {
   #          "items":[],
   #          "process_status":"done",
   #          "process_msg":"%(combination_hostName)s routing table auto uploaded" % {"combination_hostName":combination_hostName}
   #}
   #this_processor_queue.put(return_object)   
   #
   time.sleep(1)

@api_view(['GET','POST'])
@csrf_exempt
def juniper_showroute(request,format=None):

   mongo_db_collection_name = 'juniperSrx_routingTable'

   # get method
   if request.method == 'GET':

     #primaryAll_info = exact_findout('juniperSrx_devicesInfomation',{"failover" : "primary"})
     #primaryAll_info = obtainjson_from_mongodb('juniperSrx_devicesInfomation')
     #primaryAccessHost = []
     #for _dictValue_ in primaryAll_info:
     #   _value_ = str(_dictValue_[u'hostname'])
     #   if _value_ not in primaryAccessHost:
     #     primaryAccessHost.append(_value_) 
     ##
     #if not len(primaryAccessHost):
     #  return_object = {
     #     "items":[],
     #     "process_status":"error",
     #     "process_msg":"nothing to display"
     #  }
     #  print return_object
     #  return Response(json.dumps(return_object))
     #obtainjson_from_mongodb(mongo_db_collection_name),

     return_object = {
        "items": obtainjson_from_mongodb(mongo_db_collection_name),
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

         primaryAll_info = exact_findout('juniperSrx_hastatus',{"failover" : "primary"})

         primaryAccessIp = []
         for _dictValue_ in primaryAll_info:
            _value_ = str(_dictValue_[u'apiaccessip'])
            if _value_ not in primaryAccessIp:
              primaryAccessIp.append(_value_)

         # manual static route search
         _manually_items_ =[]
         _manually_registered_ = exact_findout(mongo_db_collection_name, {"update_method":"static"})
         for _dictValue_ in _manually_registered_:
            if u'_id' in _dictValue_:
              del _dictValue_[u'_id']
            _copiedValue_ = copy.copy(_dictValue_)
            _manually_items_.append(_copiedValue_)     
 
         # remove collections
         remove_collection(mongo_db_collection_name)

         if not len(primaryAccessIp):
           return_object = {
              "items":[],
              "process_status":"error",
              "process_msg":"nothing to updated for routing"
           }
           return Response(json.dumps(return_object))
        
         # queue generation
         #processing_queues_list = []
         #for _primaryip_ in primaryAccessIp:
         #   processing_queues_list.append(Queue(maxsize=0))

         # run processing to get information
         count = 0
         _processor_list_ = []
         for _primaryip_ in primaryAccessIp:
            #this_processor_queue = processing_queues_list[count]
            #_processor_ = Process(target = obtain_showroute, args = (_primaryip_, this_processor_queue, mongo_db_collection_name,))
            _processor_ = Process(target = obtain_showroute, args = (_primaryip_, mongo_db_collection_name,))
            _processor_.start()
            _processor_list_.append(_processor_)
            # for next queue
            count = count + 1
         for _processor_ in _processor_list_:
            _processor_.join()

         # manual update 
         insert_dictvalues_list_into_mongodb(mongo_db_collection_name, _manually_items_)
            
         #for _dictvalue_ in manual_static_route:
         #   insert_dictvalues_into_mongodb(mongo_db_collection_name, _dictvalue_)
         
         # get information from the queue
         #search_result = []
         #for _queue_ in processing_queues_list:
         #   while not _queue_.empty():
         #        search_result.append(_queue_.get())

         #
         return_object = {
              "items":[],
              "process_status":"",
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

