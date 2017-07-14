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
from shared_function import _defaultClustering_in_db_ as _defaultClustering_in_db_

class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders its content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)

def updateClustering_mongo(dataDict_value, this_processor_queue, mongo_db_clusterGroup_collection_name):

   hostnameValues = dataDict_value.values()
   for _hostname_ in hostnameValues:
      if len(exact_findout(mongo_db_clusterGroup_collection_name, {u'hahostname':_hostname_})):
        return_object = {
            "items":[],
            "process_status":"error",
            "process_msg":"%(_hostname_)s already clustered" % {"_hostname_":_hostname_}
        }
        this_processor_queue.put(return_object)  
        return False

   for _hostname_ in hostnameValues:
      for _element_ in exact_findout(mongo_db_clusterGroup_collection_name, {u'hostname':_hostname_}):
         if (not re.match('^none$', str(_element_[u'clusterStatus']))) or (not re.match('^none$', str(_element_[u'hahostname']))):
           return_object = {
               "items":[],
               "process_status":"error",
               "process_msg":"%(_hostname_)s has cluster member" % {"_hostname_":_hostname_}
           }
           this_processor_queue.put(return_object) 
           return False

   for _hostname_ in hostnameValues:
      for _hahostname_ in hostnameValues:
         if (not re.match(str(_hostname_),str(_hahostname_))) and (not re.match(str(_hahostname_),str(_hostname_))): 
           if len(exact_findout(mongo_db_clusterGroup_collection_name, {u'hostname':_hostname_})):
             remove_data_in_collection(mongo_db_clusterGroup_collection_name, {u'hostname':_hostname_})
           insert_dictvalues_into_mongodb(mongo_db_clusterGroup_collection_name, {u'hostname':_hostname_, u'hahostname':_hahostname_, u'clusterStatus': u'clustered'})
             
   return_object = {
      "items":[],
      "process_status":"done",
      "process_msg":"clustering done " 
   }
   this_processor_queue.put(return_object)
         

def _delete_registered_info_(dataDict_value, this_processor_queue, mongo_db_clusterGroup_collection_name):
   #
   hostnameValues = dataDict_value.values()
   for _hostname_ in hostnameValues:
      for _hahostname_ in hostnameValues:
         if (not re.match(str(_hostname_),str(_hahostname_))) and (not re.match(str(_hahostname_),str(_hostname_))):
           _dictValue_ = {u'hostname':_hostname_, u'hahostname':_hahostname_}
           print _dictValue_
           _defaultClustering_in_db_(mongo_db_clusterGroup_collection_name, _dictValue_)


@api_view(['GET','POST','DELETE'])
@csrf_exempt
def juniper_clustering(request,format=None):

   mongo_db_clusterGroup_collection_name = 'juniperSrx_clusterGroup'

   if request.method == 'GET':
     return_object = {
         "items":obtainjson_from_mongodb(mongo_db_clusterGroup_collection_name),
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
        auth_matched = re.match(ENCAP_PASSWORD, str(_input_['auth_key']))
        if auth_matched:
          if ('items' in _input_.keys()) and (u'items' in _input_.keys()):
            return_result = {}
            ## queue generation
            processing_queues_list = []
            for dataDict_value in _input_[u'items']:
               processing_queues_list.append(Queue(maxsize=0))
            # run processing to get information
            count = 0
            _processor_list_ = []
            for dataDict_value in _input_[u'items']:
               this_processor_queue = processing_queues_list[count]
               _processor_ = Process(target = updateClustering_mongo, args = (dataDict_value, this_processor_queue, mongo_db_clusterGroup_collection_name,))
               _processor_.start()
               _processor_list_.append(_processor_)
               # for next queue
               count = count + 1
            for _processor_ in _processor_list_:
               _processor_.join()
            # get information from the queue
            #search_result = []
            #for _queue_ in processing_queues_list:
            #   while not _queue_.empty():
            #        search_result.append(_queue_.get())
            #
            search_result = {
                "items":[],
                "process_status":"done",
                "process_msg":"done"
            }
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
            # queue generation
            processing_queues_list = []
            for dataDict_value in _input_[u'items']:
               processing_queues_list.append(Queue(maxsize=0))
            # run processing to get information
            count = 0
            _processor_list_ = []
            for dataDict_value in _input_[u'items']:
               this_processor_queue = processing_queues_list[count]
               _processor_ = Process(target = _delete_registered_info_, args = (dataDict_value, this_processor_queue, mongo_db_clusterGroup_collection_name,))
               _processor_.start()
               _processor_list_.append(_processor_)
               # for next queue
               count = count + 1
            for _processor_ in _processor_list_:
               _processor_.join()
            # get information from the queue
            #search_result = []
            #for _queue_ in processing_queues_list:
            #   while not _queue_.empty():
            #        search_result.append(_queue_.get())
            # return
            search_result = {
                "items":[],
                "process_status":"done",
                "process_msg":"done"
            }
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
