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
from juniperapi.setting import USER_VAR_INTERFACES

import os,re,copy,json,time,threading,sys,random
import paramiko
from multiprocessing import Process, Queue, Lock


from shared_function import runssh_clicommand as runssh_clicommand
from shared_function import sftp_file_download as sftp_file_download
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


def obtain_zonestatus(dataDict_value, mongo_db_collection_name):
   #
   #
   dictBox = copy.copy(dataDict_value);
   #
   _boxhostname_ = dictBox[u'hostname']
   _boxaccessip_ = str(dictBox[u'apiaccessip'])
   #
   #laststring_pattern = r"[ \t\n\r\f\v]+Interfaces:[ \t\n\r\f\v]+[ \t\n\r\f\va-zA-Z0-9\-\./_]+[ \t\n\r\f\v]+\{[a-zA-Z0-9]+:[a-zA-Z0-9]+\}[ \t\n\r\f\v]+"
   #securityzone_information = runssh_clicommand(_boxaccessip_, laststring_pattern, "show security zones detail | no-more\n")

   #
   _origin_filepath_ = "/var/tmp/thisHost_interfaces"
   _cmd_ = "show security zones detail | no-more | save %(_origin_filepath_)s\n" % {"_origin_filepath_":_origin_filepath_}
   laststring_pattern = "Wrote [0-9]* line[s]* of output to \'%(_origin_filepath_)s\'[ \t\n\r\f\v]+\{[a-zA-Z0-9]+:[a-zA-Z0-9]+\}[ \t\n\r\f\v]+" % {"_origin_filepath_":_origin_filepath_}
   runssh_clicommand(_boxaccessip_, laststring_pattern, _cmd_)
   _remote_filename_ = USER_VAR_INTERFACES + "interfaces@%(_primaryip_)s" % {"_primaryip_":_boxaccessip_}
   sftp_file_download(_boxaccessip_, _origin_filepath_, _remote_filename_)
   #
   f = open(_remote_filename_, 'r')
   contents = f.readlines()
   f.close()
   #
   count = 0
   zone_index_list = []
   #for _string_ in securityzone_information:
   for _string_ in contents:
      if re.search("^Security zone:", _string_, re.I):
        zone_index_list.append(count)
      count = count + 1
   #
   zone_index_count = len(zone_index_list)
   if zone_index_list[-1] < len(contents):
     zone_index_list.append(len(contents))
   #
   count = 0
   interface_index_list = []
   #for _string_ in securityzone_information:
   for _string_ in contents:
      if re.search("[ \t\n\r\f\v]+Interfaces:", _string_, re.I):
        interface_index_list.append(count + 1)
      count = count + 1
   #
   output_list = []
   for _zoneCount_ in range(len(zone_index_list) - 1):
      _nextZoneCount_ = zone_index_list[_zoneCount_ + 1]
      for _insidestring_ in contents[zone_index_list[_zoneCount_]:_nextZoneCount_]:
         _insidestring_noSpace_ = _insidestring_.strip()
         if re.search("^Security zone:", _insidestring_noSpace_, re.I):
           _zonename_ = str(_insidestring_noSpace_.split()[-1])
           for __insidestring__ in contents[interface_index_list[_zoneCount_]:_nextZoneCount_]:
              __insidestring_noSpace__ = __insidestring__.strip()
              if len(__insidestring_noSpace__) and not re.search('\{[a-zA-Z0-9]+:[a-zA-Z0-9]+\}', __insidestring_noSpace__, re.I):
                output_list.append({ 'zonename': _zonename_, 'interface': __insidestring__.strip(), 'status': 'on', "apiaccessip" : _boxaccessip_, "hostname": _boxhostname_}) 
   #
   if len(output_list):
     insert_dictvalues_list_into_mongodb(mongo_db_collection_name, output_list)
   # thread timeout 
   time.sleep(1)

@api_view(['GET','POST', 'PUT'])
@csrf_exempt
def juniper_zonestatus(request,format=None):

   mongo_db_collection_name = 'juniperSrx_zonestatus'

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
          offstatus_values = exact_findout(mongo_db_collection_name, {"status" : "off"})
          #
          data_from_databasefile = exact_findout('juniperSrx_hastatus', {"failover" : "primary"})
          #        
          # remove collection
          remove_collection(mongo_db_collection_name)

          # run processing to get information
          count = 0
          _processor_list_ = []
          for dataDict_value in data_from_databasefile:
             _processor_ = Process(target = obtain_zonestatus, args = (dataDict_value, mongo_db_collection_name))
             _processor_.start()
             _processor_list_.append(_processor_)
             count = count + 1
          for _processor_ in _processor_list_:
             _processor_.join()

          # update off values
          for dataDict_value in offstatus_values:
             _copied_value_ = copy.copy(dataDict_value)
             if u'status' in _copied_value_:
               _copied_value_[u'status'] = unicode('on')
             if u'_id' in _copied_value_:
               del _copied_value_[u'_id']

             for _innerDict_ in exact_findout(mongo_db_collection_name, _copied_value_):
                dataDict_value[u'_id'] = _innerDict_[u'_id']
                replace_dictvalues_into_mongodb(mongo_db_collection_name, _innerDict_, dataDict_value)
             
          return_object = {
             "items":[],
             "process_status":"done",
             "process_msg":"done"
          }
          return Response(json.dumps(return_object))

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

          for _inner_ in _thisGet_value_:
             _copied_inner_ = copy.copy(_inner_)
             _statusString_ = str(_copied_inner_[u'status'])

             if re.match('on', _statusString_, re.I):
               _copied_inner_[u'status'] = unicode('off')

             if re.match('off', _statusString_, re.I):
               _copied_inner_[u'status'] = unicode('on')

             replace_dictvalues_into_mongodb(mongo_db_collection_name, _inner_, _copied_inner_)
          #
          return_object = {
             "items":[],
             "process_status":"done",
             "process_msg":"done"
          }
          return Response(json.dumps(return_object))

        # end of if auth_matched:
        else:
          return_object = {"items":[{"message":"no authorization!","process_status":"error"}]}
          return Response(json.dumps(return_object))
      # end of if re.search(r"system", system_property["role"], re.I):
      else:
        return_object = {"items":[{"message":"this host has no authorizaition!","process_status":"error"}]}
        return Response(json.dumps(return_object))

