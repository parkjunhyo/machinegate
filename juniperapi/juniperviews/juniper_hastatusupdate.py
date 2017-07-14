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


def obtain_hastatus(dataDict_value, mongo_db_collection_name):
   #
   dictBox = copy.copy(dataDict_value);
   #
   laststring_pattern = r"[ \t\n\r\f\v]+Online[ \t\n\r\f\v]+[ \t\n\r\f\va-zA-Z0-9\-\./_\+\(\)]+[ \t\n\r\f\v]+\{[a-zA-Z0-9]+:[a-zA-Z0-9]+\}[ \t\n\r\f\v]+"
   securityzone_information = runssh_clicommand(dictBox[u'apiaccessip'], laststring_pattern, "show chassis fpc pic-status | no-more\n")
 
   #
   nodehastatus_pettern = r"{([a-zA-Z0-9]+):([a-zA-Z0-9]+)\}"
   match_values = {}
   for _string_ in securityzone_information:
      _searched_ = re.search(nodehastatus_pettern, _string_, re.I)
      if _searched_:
        match_values[u'apiaccessip'] = dictBox[u'apiaccessip']
        match_values[u'hostname'] = dictBox[u'hostname']
        match_values[u'failover'] = unicode(_searched_.group(1))
        match_values[u'node'] = unicode(_searched_.group(2))
        break
    
   if match_values:
     insert_dictvalues_into_mongodb(mongo_db_collection_name, match_values)
 
   # thread timeout 
   time.sleep(1)


@api_view(['GET','POST'])
@csrf_exempt
def juniper_hastatusupdate(request,format=None):

   dbCollectionName = 'juniperSrx_hastatus'

   if request.method == 'GET':
     return_object = {
         "items":obtainjson_from_mongodb(dbCollectionName),
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
          data_from_databasefile = obtainjson_from_mongodb('juniperSrx_registeredDevices')
 
          # remove collection
          remove_collection(dbCollectionName)

          # run processing to get information
          count = 0
          _processor_list_ = []
          for dataDict_value in data_from_databasefile:
             _processor_ = Process(target = obtain_hastatus, args = (dataDict_value, dbCollectionName))
             _processor_.start()
             _processor_list_.append(_processor_)
             count = count + 1
          for _processor_ in _processor_list_:
             _processor_.join()

          #
          return_object = {
              "items":[],
              "process_status":"done",
              "process_msg":"done"
          }
          #
          return Response(json.dumps(return_object))

        # end of if auth_matched:
        else:
          return_object = {"items":[{"message":"no authorization!","process_status":"error"}]}
          return Response(json.dumps(return_object))
      # end of if re.search(r"system", system_property["role"], re.I):
      else:
        return_object = {"items":[{"message":"this host has no authorizaition!","process_status":"error"}]}
        return Response(json.dumps(return_object))
