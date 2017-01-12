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
from juniperapi.setting import USER_VAR_NAT 
from juniperapi.setting import USER_VAR_CHCHES


import os,re,copy,json,time,threading,sys
import paramiko
from multiprocessing import Process, Queue, Lock
from netaddr import *

class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders its content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)


def start_end_parse_from_string(return_lines_string,pattern_start,pattern_end):
   start_end_linenumber_list = []
   line_index_count = 0
   temp_list_box = []
   for _line_string_ in return_lines_string:
      if re.search(pattern_start,_line_string_,re.I):
        temp_list_box.append(line_index_count)
      if re.search(pattern_end,_line_string_,re.I):
        temp_list_box.append(line_index_count)
        start_end_linenumber_list.append(temp_list_box)
        temp_list_box = []
      line_index_count = line_index_count + 1
   return start_end_linenumber_list

def start_end_parse_from_string_endlist(return_lines_string,pattern_start,pattern_end_list):
   start_end_linenumber_list = []
   line_index_count = 0
   temp_list_box = []
   for _line_string_ in return_lines_string:
      if re.search(pattern_start,_line_string_,re.I):
        temp_list_box.append(line_index_count)
      for pattern_end in pattern_end_list:
         if re.search(str(pattern_end),str(_line_string_),re.I):
           temp_list_box.append(line_index_count)
           start_end_linenumber_list.append(temp_list_box)
           temp_list_box = []
           break
      line_index_count = line_index_count + 1
   return start_end_linenumber_list


def searched_ip_pattern(inner_msg_string_, searched_ip_list):
   searched_portstatus = re.search("([0-9]+.[0-9]+.[0-9]+.[0-9]+)[ \t\n\r\f\v]+\-[ \t\n\r\f\v]+([0-9]+.[0-9]+.[0-9]+.[0-9]+)", inner_msg_string_, re.I)
   if searched_portstatus:
     ip_list = list(iter_iprange(str(searched_portstatus.group(1)), str(searched_portstatus.group(2))))
     for _netip_ in ip_list:
        _netip_string_ = str(_netip_).strip()
        if _netip_string_ not in searched_ip_list:
          searched_ip_list.append(_netip_string_)   
   return searched_ip_list

def findout_iplist_from_range(selective_list, inner_pattern_start, inner_pattern_end):
   searched_ip_list = []
   inner_start_end_linenumber_list = start_end_parse_from_string(selective_list, inner_pattern_start, inner_pattern_end)
   for inner_index_list in inner_start_end_linenumber_list:
      inner_selective_list = selective_list[inner_index_list[0]:inner_index_list[-1]]
      for inner_msg_string_ in inner_selective_list:
         searched_ip_list = searched_ip_pattern(inner_msg_string_, searched_ip_list)
   return searched_ip_list

def cachingnat_processing(_accessip_, _hostname_):
   #
   filestring_pattern = "%(_hostname_)s@%(_ipaddress_)s" % {"_ipaddress_":_accessip_, "_hostname_":_hostname_}
   filenames_list_indirectory = os.listdir(USER_VAR_NAT)
   valied_filename = []
   for _filename_ in filenames_list_indirectory:
      if re.search(filestring_pattern, str(_filename_), re.I):
        searched_filename = USER_VAR_NAT + _filename_
        if searched_filename not in valied_filename:
          valied_filename.append(searched_filename)


   for _filename_ in valied_filename:

      if re.search(".nat.static.rule", _filename_, re.I):
        natcache_memory = {}
        #
        f = open(_filename_, "r")
        read_contents = f.readlines()
        f.close()
        #
        pattern_start = "Static NAT rule:"
        pattern_end = "Number of sessions[ \t\n\r\f\v]+:"
        start_end_linenumber_list = start_end_parse_from_string(read_contents, pattern_start, pattern_end)
        for index_list in start_end_linenumber_list:
           # range to items
           selective_list = read_contents[index_list[0]:index_list[-1]+int(1)]
           # default init
           _natrulename_ = "unknown"
           _natrulesetname_ = "unknown"
           _fromzonename_ = "unknown"
           _destaddress_ = "unknown"
           _hostaddress_ = "unknown"
           _netmask_ = "unknown"
           # analysis each line of the one items
           for _msg_string_ in selective_list:
              compare_string = _msg_string_.strip()
              splited_compare_string = compare_string.split()
              if re.search("Static NAT rule:", compare_string, re.I):
                _natrulename_ = splited_compare_string[3] 
                _natrulesetname_ = splited_compare_string[-1]
              if re.search("From zone", compare_string, re.I):
                _fromzonename_ = splited_compare_string[-1]
              if re.search("Destination addresses", compare_string, re.I):
                _destaddress_ = splited_compare_string[-1]
              if re.search("Host addresses", compare_string, re.I):
                _hostaddress_ = splited_compare_string[-1]
              if re.search("Netmask", compare_string, re.I):
                _netmask_ = splited_compare_string[-1]
           # change to values 
           _ruleunique_ = "%(_natrulename_)s:%(_natrulesetname_)s" % {"_natrulename_":_natrulename_, "_natrulesetname_":_natrulesetname_}
           _destaddress_string_ = "%(_destaddress_)s/%(_netmask_)s@%(_hostname_)s:static_from_%(_fromzonename_)s@%(_ruleunique_)s" % {"_destaddress_":_destaddress_, "_hostname_":_hostname_, "_fromzonename_":_fromzonename_, "_netmask_":_netmask_, "_ruleunique_":_ruleunique_}
           _hostaddress_string_ = "%(_hostaddress_)s/%(_netmask_)s@%(_hostname_)s:static_from_%(_fromzonename_)s@%(_ruleunique_)s" % {"_hostaddress_":_hostaddress_, "_hostname_":_hostname_, "_fromzonename_":_fromzonename_, "_netmask_":_netmask_, "_ruleunique_":_ruleunique_}
           # 
           keyname_string = "%(_ipaddrvalue_)s/%(_netmask_)s" % {"_netmask_":_netmask_,"_ipaddrvalue_":_destaddress_}
           if keyname_string  not in natcache_memory.keys():
             natcache_memory[keyname_string] = []
           natcache_memory[keyname_string].append(_hostaddress_string_)

           keyname_string = "%(_ipaddrvalue_)s/%(_netmask_)s" % {"_netmask_":_netmask_,"_ipaddrvalue_":_hostaddress_}
           if keyname_string not in natcache_memory.keys():
             natcache_memory[keyname_string] = []           
           natcache_memory[keyname_string].append(_destaddress_string_)
        #
        saved_filename = _filename_.strip().split("/")[-1]
        filename_string = "cachenat_%(saved_filename)s.txt" % {"saved_filename":str(saved_filename)}
        JUNIPER_DEVICELIST_DBFILE = USER_VAR_CHCHES + filename_string
        f = open(JUNIPER_DEVICELIST_DBFILE,"w")
        f.write(json.dumps(natcache_memory))
        f.close() 

      if re.search(".nat.source.rule", _filename_, re.I):
        natcache_memory = {}
        #
        sourcepool_filename = _filename_.strip().split(".nat.source.rule")[0] + ".nat.source.pool"
        f = open(sourcepool_filename, "r")
        read_contents = f.readlines()
        f.close()
        #
        pattern_start = "Pool name[ \t\n\r\f\v]+:"
        pattern_end = "Address range"
        start_end_linenumber_list = start_end_parse_from_string(read_contents, pattern_start, pattern_end)
        sourcepool_memory = {}
        for index_list in start_end_linenumber_list:
           # range to items
           selective_list = read_contents[index_list[0]:index_list[-1]+int(2)]
           # default init
           _poolname_ = "unknown"
           _sourceport_ = "unknown"
           _sourceip_ = []
           for _msg_string_ in selective_list:
              compare_string = _msg_string_.strip()
              if re.search("Pool name[ \t\n\r\f\v]+:", compare_string, re.I):
                _poolname_ = compare_string.split()[-1]
              searched_portstatus = re.search("^Port[ \t\n\r\f\v]+:[ \t\n\r\f\v]+\[([0-9]+),[ \t\n\r\f\v]+([0-9]+)\]", compare_string, re.I)
              if searched_portstatus:
                _sourceport_ = "%(_start_)s:%(_finish_)s" % {"_start_":str(searched_portstatus.group(1)), "_finish_":str(searched_portstatus.group(2))} 
              _sourceip_ = searched_ip_pattern(compare_string, _sourceip_) 
           #  
           if _poolname_ not in sourcepool_memory.keys():
             sourcepool_memory[_poolname_] = []
           for _ip_ in _sourceip_:
              member_string = "%(_ip_)s_%(_sourceport_)s" % {"_ip_":_ip_, "_sourceport_":_sourceport_}
              if member_string not in sourcepool_memory[_poolname_]:
                sourcepool_memory[_poolname_].append(member_string)

        #_filename_
        f = open(_filename_, "r")
        read_contents = f.readlines()
        f.close()
        #
        pattern_start = "source NAT rule:"
        pattern_end = "Number of sessions[ \t\n\r\f\v]+:"
        start_end_linenumber_list = start_end_parse_from_string(read_contents, pattern_start, pattern_end)

        for index_list in start_end_linenumber_list:
           # range to items
           selective_list = read_contents[index_list[0]:index_list[-1]+int(1)]
           # source and destination address
           _sourceipvaluelist_ = findout_iplist_from_range(selective_list, "Source addresses[ \t\n\r\f\v]+:", "Destination addresses[ \t\n\r\f\v]+:")
           # init value
           _natrulename_ = "unknown"
           _natrulesetname_ = "unknown"
           _fromzonename_ = "unknown"
           _tozonename_ = "unknown"
           _action_ = "unknown"
           # analysis each line of the one items
           for _msg_string_ in selective_list:
              compare_string = _msg_string_.strip()
              splited_compare_string = compare_string.split()
              if re.search("source NAT rule:", compare_string, re.I):
                _natrulename_ = splited_compare_string[3]
                _natrulesetname_ = splited_compare_string[-1]
              if re.search("From zone[ \t\n\r\f\v]+:", compare_string, re.I):
                _fromzonename_ = splited_compare_string[-1]
              if re.search("To zone[ \t\n\r\f\v]+:", compare_string, re.I):
                _tozonename_ = splited_compare_string[-1]
              if re.search("Action[ \t\n\r\f\v]+:", compare_string, re.I):
                _action_ = splited_compare_string[-1]
           # 
           _ruleunique_ = "%(_natrulename_)s:%(_natrulesetname_)s" % {"_natrulename_":_natrulename_, "_natrulesetname_":_natrulesetname_} 
           for _srcip_ in _sourceipvaluelist_:
              _srcip_string_ = "%(_srcip_)s/32" % {"_srcip_":_srcip_}
              if _srcip_string_ not in natcache_memory.keys():
                natcache_memory[_srcip_string_] = []
              for _targetip_ in sourcepool_memory[_action_]:
                 _targetip_value_ = str(_targetip_.strip().split("_")[0])
                 _targetip_string_ = "%(_targetip_value_)s/32@%(_hostname_)s:source_from_%(_fromzonename_)s_to_%(_tozonename_)s@%(_ruleunique_)s" % {"_targetip_value_":_targetip_value_, "_hostname_":_hostname_, "_fromzonename_":_fromzonename_, "_tozonename_":_tozonename_, "_ruleunique_":_ruleunique_}
                 if _targetip_string_ not in natcache_memory[_srcip_string_]:
                   natcache_memory[_srcip_string_].append(_targetip_string_) 
           # 
           for _targetip_ in sourcepool_memory[_action_]:
              _targetip_value_ = str(_targetip_.strip().split("_")[0])
              _targetip_string_ = "%(_targetip_value_)s/32" % {"_targetip_value_":_srcip_}
              if _targetip_string_ not in natcache_memory.keys():
                natcache_memory[_targetip_string_] = []
              for _srcip_ in _sourceipvaluelist_:
                 _srcip_string_ = "%(_srcip_)s/32@%(_hostname_)s:source_from_%(_fromzonename_)s_to_%(_tozonename_)s@%(_ruleunique_)s" % {"_srcip_":_srcip_, "_hostname_":_hostname_, "_fromzonename_":_fromzonename_, "_tozonename_":_tozonename_, "_ruleunique_":_ruleunique_}
                 if _srcip_string_ not in natcache_memory[_targetip_string_]:
                   natcache_memory[_targetip_string_].append(_srcip_string_)

        #
        saved_filename = _filename_.strip().split("/")[-1]
        filename_string = "cachenat_%(saved_filename)s.txt" % {"saved_filename":str(saved_filename)}
        JUNIPER_DEVICELIST_DBFILE = USER_VAR_CHCHES + filename_string
        f = open(JUNIPER_DEVICELIST_DBFILE,"w")
        f.write(json.dumps(natcache_memory))
        f.close()
        #


   # thread timeout 
   time.sleep(1)

def viewer_information():

   filenames_list = os.listdir(USER_VAR_CHCHES)
   updated_filestatus = {}
   filestatus = False
   for _filename_ in filenames_list:
      searched_element = re.search("cachepolicy_",_filename_,re.I)
      if searched_element:
        filepath = USER_VAR_CHCHES + _filename_
        updated_filestatus[str(_filename_)] = str(time.ctime(os.path.getmtime(filepath)))
        filestatus = True

   if not filestatus:
     return ["error, caching the policy!, but before caching need export policy from devices"] 

   return updated_filestatus 


@api_view(['GET','POST'])
@csrf_exempt
def juniper_cachingnat(request,format=None):

   JUNIPER_DEVICELIST_DBFILE = USER_DATABASES_DIR + "devicelist.txt"

   # get method
   if request.method == 'GET':
      try:

         return Response(viewer_information())

      except:
         message = ["error, viewer has some issue!"]
         return Response(message, status=status.HTTP_400_BAD_REQUEST)


   elif request.method == 'POST':

      try:
        _input_ = JSONParser().parse(request)

        if re.match(ENCAP_PASSWORD,str(_input_[0]['auth_key'])):

           # log message
           #f = open(LOG_FILE,"a")
           #_date_ = os.popen("date").read().strip()
           #log_msg = _date_+" from : "+request.META['REMOTE_ADDR']+" , method POST request to run f5_devicelist function!\n"
           #f.write(log_msg)
           #f.close()

           # device file read
           CURL_command = "curl http://0.0.0.0:"+RUNSERVER_PORT+"/juniper/devicelist/"
           get_info = os.popen(CURL_command).read().strip()
           stream = BytesIO(get_info)
           data_from_CURL_command = JSONParser().parse(stream)

           ## policy database file comes from standby device! 
           ## at this time, seconday should be used to match for working
           valid_access_ip = []
           ip_device_dict = {}
           for dataDict_value in data_from_CURL_command:
              _keyname_ = dataDict_value.keys()
              if (u"failover" not in _keyname_) or ("failover" not in _keyname_):
                return Response("error, device list should be updated!", status=status.HTTP_400_BAD_REQUEST)
              else:
                searched_element = re.search(str("secondary"),str(dataDict_value[u"failover"]),re.I)
                if searched_element:
                  _ipaddress_ = str(dataDict_value[u"apiaccessip"])
                  if _ipaddress_ not in valid_access_ip:
                    ip_device_dict[_ipaddress_] = str(dataDict_value[u"devicehostname"])
                    valid_access_ip.append(_ipaddress_)

           _processor_list_ = []
           for _accessip_ in valid_access_ip:
              _processor_ = Process(target = cachingnat_processing, args = (_accessip_, ip_device_dict[_accessip_],))
              _processor_.start()
              _processor_list_.append(_processor_) 
           for _processor_ in _processor_list_:
              _processor_.join()


           # return
           return Response(viewer_information())

      except:
        message = "Post Algorithm has some problem!"
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

