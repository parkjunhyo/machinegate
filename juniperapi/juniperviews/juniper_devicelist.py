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

import os,re,copy,json,time,threading,sys,random
import paramiko
from multiprocessing import Process, Queue, Lock


from shared_function import runssh_clicommand as runssh_clicommand
from shared_function import update_dictvalues_into_mongodb as update_dictvalues_into_mongodb 
from shared_function import obtainjson_from_mongodb as obtainjson_from_mongodb 
from shared_function import remove_collection as remove_collection

class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders its content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)


def obtain_deviceinfo(dataDict_value, this_processor_queue):
   # the box for the return
   dictBox = {}
   #  
   dictBox[u'apiaccessip'] = dataDict_value[u'apiaccessip']
   dictBox[u'location'] = dataDict_value[u'location']
   dictBox[u'model'] = dataDict_value[u'model']
   dictBox[u'version'] = dataDict_value[u'version']
   dictBox[u'devicehostname'] = dataDict_value[u'hostname']
   #
   laststring_pattern = r"[ \t\n\r\f\v]+Interfaces:[ \t\n\r\f\v]+[ \t\n\r\f\va-zA-Z0-9\-\./_]+[ \t\n\r\f\v]+\{[a-zA-Z0-9]+:[a-zA-Z0-9]+\}[ \t\n\r\f\v]+"
   securityzone_information = runssh_clicommand(dictBox[u'apiaccessip'], laststring_pattern, "show security zones detail | no-more\n")
   #
   laststring_pattern = r"[0-9]+.[0-9]+.[0-9]+.[0-9]+/[0-9]+[ \t\n\r\f\v]+\{[a-zA-Z0-9]+:[a-zA-Z0-9]+\}[ \t\n\r\f\v]+"
   nodegroup_information = runssh_clicommand(dictBox[u'apiaccessip'], laststring_pattern, "show configuration groups | display set | match node | match interface | match fxp | match address\n")

   stringcombination = str("".join(nodegroup_information))
   # node name and failover name : {primary:node0} and {secondary:node1} will be expected!
   pattern_search = "{(\w+):(\w+)}"
   searched_element = re.search(pattern_search, stringcombination, re.I)
   if searched_element:
     dictBox[u'failover'] = searched_element.group(1).strip()
     dictBox[u'nodeid'] = searched_element.group(2).strip()

   # cluster ip address : u'hadevicesip': ['10.10.77.54:node1'] will be expected!
   stringcombination_splitedbyenter = stringcombination.split('/');
   pattern_search = "set groups (node[0-9]+) interfaces"
   clusterinfo = {}
   for _string_ in stringcombination_splitedbyenter:
      searched_element = re.search(pattern_search, _string_, re.I)
      if searched_element:
        searched_element.group(1).strip()
        clusterinfo[searched_element.group(1).strip()] = str(_string_.split()[-1]).strip()
   clusterlist = []
   for _keyname_ in clusterinfo.keys():
      if not re.match(_keyname_, dictBox[u'nodeid'], re.I):
        if clusterinfo[_keyname_] not in clusterlist:
          clusterlist.append(clusterinfo[_keyname_])   
   dictBox[u'hadevicesip'] = clusterlist   
   
   # findout the start index for Security zone and Interfaces
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
   # findout interface and zone : {u'zonesinfo': {'PRI': {'reth1.0': ['10.10.78.116/29']}, 'PCI': {'reth3.0': ['10.10.78.137/29']}}} is expected!
   zone_info_dict = {}
   for _index_ in range(zone_index_count):
      _zonename_ = (securityzone_information[zone_index_list[_index_]].strip().split()[-1])
      if not re.search(r"junos-host", _zonename_, re.I):
        if _zonename_ not in zone_info_dict.keys():
          zone_info_dict[_zonename_] = {}
        iface_start = interface_index_list[_index_]+1
        iface_end = zone_index_list[_index_+1] 
        paragaph_group = securityzone_information[iface_start:iface_end]
        for _string_ in paragaph_group:
           _ifname_ = _string_.strip()
           if not re.search(r"[ \t\n\r\f\v]*\{[a-zA-Z0-9]+:[a-zA-Z0-9]+\}[ \t\n\r\f\v]*", _ifname_, re.I):
             if len(_ifname_) and (_ifname_ not in zone_info_dict[_zonename_].keys()):
               clicommand = "show interfaces %(_ifname_)s terse | no-more\n" % {"_ifname_":_ifname_}
               laststring_pattern = "%(_ifname_)s[ \t\n\r\f\va-zA-Z0-9\-\.\/\_\<\>\-\:\*\[\]]*[ \t\n\r\f\v]+\{[a-zA-Z0-9]+:[a-zA-Z0-9]+\}[ \t\n\r\f\v]+" % {"_ifname_":_ifname_}
               interface_information = runssh_clicommand(dictBox[u'apiaccessip'], laststring_pattern, clicommand)
               zone_info_dict[_zonename_][_ifname_] = []
               for _line_content_ in interface_information:
                  searched_element = re.search('(inet[0-9]*)', _line_content_, re.I)
                  if searched_element:
                    _string_included_ = _line_content_.split(searched_element.group(1).strip())[-1].strip()
                    zone_info_dict[_zonename_][_ifname_].append(_string_included_.split()[0])
   dictBox[u'zonesinfo'] = zone_info_dict 

   # result return using the queue
   done_msg = "%(apiaccessip_from_in)s device information re-created!" % {"apiaccessip_from_in":dictBox[u'apiaccessip']}
   this_processor_queue.put({"message":done_msg,"process_status":"done","process_done_items":dictBox})

   # thread timeout 
   time.sleep(2)


@api_view(['GET','POST'])
@csrf_exempt
def juniper_devicelist(request,format=None):

   mongo_db_collection_name = 'juniper_srx_devices'

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
          #
          data_from_databasefile = obtainjson_from_mongodb('juniper_srx_registered_ip')
          # queue generation
          processing_queues_list = []
          for dataDict_value in data_from_databasefile:
             processing_queues_list.append(Queue(maxsize=0))
          # run processing to get information
          count = 0
          _processor_list_ = []
          for dataDict_value in data_from_databasefile:
             this_processor_queue = processing_queues_list[count]
             _processor_ = Process(target = obtain_deviceinfo, args = (dataDict_value, this_processor_queue,))
             _processor_.start()
             _processor_list_.append(_processor_)
             count = count + 1
          for _processor_ in _processor_list_:
             _processor_.join()
          # get information from the queue
          search_result = []
          return_values = []
          for _queue_ in processing_queues_list:
             while not _queue_.empty():
                  _get_values_ = _queue_.get()
                  if re.search(str(_get_values_["process_status"]),"done",re.I) or re.search(str(_get_values_[u"process_status"]),"done",re.I):
                    search_result.append(_get_values_["process_done_items"])
                    return_values.append(_get_values_)
          if len(search_result):
            update_dictvalues_into_mongodb(mongo_db_collection_name, search_result)
          else:
            return_values = [{"message":"all of devices information cleared!", "process_status":"done"}]
            remove_collection(mongo_db_collection_name)
          return Response(json.dumps({"items":return_values}))
        # end of if auth_matched:
        else:
          return_object = {"items":[{"message":"no authorization!","process_status":"error"}]}
          return Response(json.dumps(return_object))
      # end of if re.search(r"system", system_property["role"], re.I):
      else:
        return_object = {"items":[{"message":"this host has no authorizaition!","process_status":"error"}]}
        return Response(json.dumps(return_object))
          
 
