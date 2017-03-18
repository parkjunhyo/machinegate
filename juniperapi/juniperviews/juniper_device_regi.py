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
from juniperapi.setting import PARAMIKO_DEFAULT_TIMEWAIT
from juniperapi.setting import system_property 
from juniperapi.setting import paramiko_conf as paramiko_conf

import os,re,copy,json,time,threading,sys,random
import paramiko
from multiprocessing import Process, Queue, Lock


from shared_function import start_end_parse_from_string as start_end_parse_from_string
from shared_function import runssh_clicommand as runssh_clicommand
from shared_function import obtainjson_from_mongodb as obtainjson_from_mongodb 
from shared_function import insert_dictvalues_into_mongodb as insert_dictvalues_into_mongodb
from shared_function import remove_data_in_collection as remove_data_in_collection
from shared_function import exact_findout as exact_findout
from shared_function import remove_info_in_db as remove_info_in_db


class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders its content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)

def confirm_ip_reachable(_dictvalues_, this_processor_queue, registered_ip_string, registered_ip_unicode):
   # parse values
   apiaccessip_from_in = str(_dictvalues_[u'apiaccessip'])
   location_from_in = str(_dictvalues_[u'location'])
   # check the accessable status
   remote_conn_pre = paramiko.SSHClient()
   remote_conn_pre.set_missing_host_key_policy(paramiko.AutoAddPolicy())
   try:
     remote_conn_pre.connect(apiaccessip_from_in, username=USER_NAME, password=USER_PASSWORD, look_for_keys=False, allow_agent=False, timeout=paramiko_conf["connect_timeout"])
     remote_conn_pre.close()
     laststring_pattern = "JUNOS Software Release[ \t\n\r\f\va-zA-Z0-9\-\.\/\_\<\>\-\:\*\[\]]*[ \t\n\r\f\v]+\{[a-zA-Z0-9]+:[a-zA-Z0-9]+\}[ \t\n\r\f\v]+"
     interface_information = runssh_clicommand(apiaccessip_from_in, laststring_pattern, "show version | no-more\n")
     _hostname_ = ''
     for _string_ in interface_information:
        hostname_pattern = "@([ \t\n\r\f\va-zA-Z0-9\-\.\/\_\<\>\-\:\*\[\]]+)[>#]+"
        searched_element = re.search(hostname_pattern, _string_)
        if searched_element:
          _hostname_ = searched_element.group(1).strip()
          break
     _hwmodel_ = ''
     _hwversion_ = ''
     for _index_pair_ in start_end_parse_from_string(interface_information, "Hostname: ", "JUNOS Software Release "):
        if re.search("Hostname: %(_hostname_)s" % {"_hostname_":_hostname_}, interface_information[_index_pair_[0]]):
          _hwmodel_ = str(str(interface_information[_index_pair_[0]+1]).split()[-1]).strip()
          _hwversion_ = re.search("\[([a-zA-Z0-9\-\.\/\_\<\>\-\:\*]*)\]", interface_information[_index_pair_[-1]]).group(1).strip()
     #
     if (_dictvalues_[u'apiaccessip'] not in registered_ip_string) or (_dictvalues_[u'apiaccessip'] not in registered_ip_unicode):
       ## input values for mongo database : 
       mongodb_input = {u'apiaccessip':apiaccessip_from_in, u'hostname':_hostname_, u'location':location_from_in, u'model':_hwmodel_, u'version':_hwversion_}
       done_msg = "%(apiaccessip_from_in)s device registered!" % {"apiaccessip_from_in":apiaccessip_from_in}
       ## return the queue
       this_processor_queue.put({"message":done_msg,"process_status":"done","process_done_items":mongodb_input})
     else:
       error_msg = "%(apiaccessip_from_in)s already registered!" % {"apiaccessip_from_in":apiaccessip_from_in}
       ## return the queue
       this_processor_queue.put({"message":error_msg,"process_status":"error"})
     # end of try:
   except:
     print "-------10----------"
     remote_conn_pre.close()
     error_msg = "%(apiaccessip_from_in)s not reachable address!" % {"apiaccessip_from_in":apiaccessip_from_in}
     this_processor_queue.put({"message":error_msg,"process_status":"error"})
   # end of def confirm_ip_reachable(_dictvalues_, this_processor_queue, registered_ip_string, registered_ip_unicode, mongo_db_collection_name):
     

@api_view(['GET','POST','DELETE'])
@csrf_exempt
def juniper_device_regi(request,format=None):

   mongo_db_collection_name = 'juniper_srx_registered_ip'

   if request.method == 'GET':
     return_result = {"items":obtainjson_from_mongodb(mongo_db_collection_name)}
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
          if ('items' in _input_.keys()) and (u'items' in _input_.keys()):
            return_result = {}
            # from database
            registered_info_from_mongodb = obtainjson_from_mongodb(mongo_db_collection_name)
            #
            registered_ip_string = []
            registered_ip_unicode = []
            for _dictvalues_ in registered_info_from_mongodb:
               registered_ip_string.append(str(_dictvalues_[u'apiaccessip']))
               registered_ip_unicode.append(_dictvalues_[u'apiaccessip'])
            # queue generation
            processing_queues_list = []
            for dataDict_value in _input_[u'items']:
               processing_queues_list.append(Queue(maxsize=0))
            # run processing to get information
            count = 0
            _processor_list_ = []
            for dataDict_value in _input_[u'items']:
               this_processor_queue = processing_queues_list[count]
               _processor_ = Process(target = confirm_ip_reachable, args = (dataDict_value, this_processor_queue, registered_ip_string, registered_ip_unicode,))
               _processor_.start()
               _processor_list_.append(_processor_)
               # for next queue
               count = count + 1
            for _processor_ in _processor_list_:
               _processor_.join()
            # get information from the queue
            search_result = []
            for _queue_ in processing_queues_list:
               while not _queue_.empty():
                    _get_values_ = _queue_.get()
                    if re.search(str(_get_values_["process_status"]),"done",re.I) or re.search(str(_get_values_[u"process_status"]),"done",re.I):
                      # expected value : {u'apiaccessip':, u'hostname':, u'location':, u'model':, u'version':} 
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
            for dataDict_value in _input_[u'items']:
               processing_queues_list.append(Queue(maxsize=0))
            # run processing to get information
            count = 0
            _processor_list_ = []
            for dataDict_value in _input_[u'items']:
               this_processor_queue = processing_queues_list[count]
               _processor_ = Process(target = remove_info_in_db, args = (dataDict_value, this_processor_queue, mongo_db_collection_name,))
               _processor_.start()
               _processor_list_.append(_processor_)
               # for next queue
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
