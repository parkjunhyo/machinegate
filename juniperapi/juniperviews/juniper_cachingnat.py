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

def lineanaysis_getlast_value(_pattern_string_, compare_string, last_string):
   splited_compare_string = compare_string.split()
   if re.search(_pattern_string_, compare_string, re.I):
     last_string = splited_compare_string[-1]
   return last_string

def rule_information(_pattern_string_, compare_string, _natrulename_, _natrulesetname_):
   if re.search(_pattern_string_, compare_string, re.I):
     spliated_pattern_string_ = compare_string.strip().split(":")
     _natrulename_ = str(spliated_pattern_string_[1].strip().split()[0]).strip()
     _natrulesetname_ = spliated_pattern_string_[-1].strip()
   return [_natrulename_, _natrulesetname_]  

def fillvalues_withkeyname(keyname_string, natcache_memory, insert_values):
   if keyname_string  not in natcache_memory.keys():
     natcache_memory[keyname_string] = []
   if insert_values not in natcache_memory[keyname_string]:
     natcache_memory[keyname_string].append(insert_values)
   return natcache_memory

def fillvalues_sourceinfo_withkeyname(_firstloop_, _secondloop_, natcache_memory, _netmask_, _hostname_, _fromzonename_, _tozonename_, _ruleunique_, source_unique_string):
   for _srcip_ in _firstloop_:
      keyname_string = "%(_ipaddress_)s/%(_netmask_)s" % {"_ipaddress_":str(_srcip_).strip(),"_netmask_":_netmask_}
      for _ipaddress_ in _secondloop_:
         insert_values = source_unique_string % {"_ipaddress_":_ipaddress_, "_netmask_":_netmask_,  "_hostname_":_hostname_, "_fromzonename_":_fromzonename_, "_tozonename_":_tozonename_, "_ruleunique_":_ruleunique_}
         natcache_memory = fillvalues_withkeyname(keyname_string, natcache_memory, insert_values)
   return natcache_memory

def savethefile_dictvalueinput(_filename_, natcache_memory):
   saved_filename = _filename_.strip().split("/")[-1]
   filename_string = "cachenat_%(saved_filename)s.txt" % {"saved_filename":str(saved_filename)}
   JUNIPER_DEVICELIST_DBFILE = USER_VAR_CHCHES + filename_string
   f = open(JUNIPER_DEVICELIST_DBFILE,"w")
   f.write(json.dumps(natcache_memory))
   f.close()

def readfile_getcontents(_filename_):
   f = open(_filename_, "r")
   read_contents = f.readlines()
   f.close()
   return read_contents

def getsourcepoolmember_info(start_end_linenumber_list, read_contents):
   sourcepool_memory = {}
   for index_list in start_end_linenumber_list:
      selective_list = read_contents[index_list[0]:index_list[-1]+int(2)]
      _poolname_ = "unknown"
      _sourceip_ = []
      for _msg_string_ in selective_list:
         compare_string = _msg_string_.strip()
         _poolname_ = lineanaysis_getlast_value("Pool name[ \t\n\r\f\v]+:", compare_string, _poolname_)
         _sourceip_ = searched_ip_pattern(compare_string, _sourceip_)
      for _ip_ in _sourceip_:
         sourcepool_memory = fillvalues_withkeyname(_poolname_, sourcepool_memory, _ip_)
   return sourcepool_memory


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
        read_contents = readfile_getcontents(_filename_)
        #
        natcache_memory = {}
        pattern_start = "Static NAT rule:"
        pattern_end = "Number of sessions[ \t\n\r\f\v]+:"
        start_end_linenumber_list = start_end_parse_from_string(read_contents, pattern_start, pattern_end)
        for index_list in start_end_linenumber_list:
           # range to items
           selective_list = read_contents[index_list[0]:index_list[-1]+int(1)]
           # init values
           [_natrulename_, _natrulesetname_, _fromzonename_, _destaddress_, _hostaddress_, _netmask_] = ["unknown", "unknown", "unknown", "unknown", "unknown", "unknown"]
           # analysis each line of the one items
           for _msg_string_ in selective_list:
              compare_string = _msg_string_.strip()
              [_natrulename_, _natrulesetname_] = rule_information("Static NAT rule:", compare_string, _natrulename_, _natrulesetname_)
              _fromzonename_ = lineanaysis_getlast_value("From zone", compare_string, _fromzonename_)
              _destaddress_ = lineanaysis_getlast_value("Destination addresses", compare_string, _destaddress_)
              _hostaddress_ = lineanaysis_getlast_value("Host addresses", compare_string, _hostaddress_)
              _netmask_ = lineanaysis_getlast_value("Netmask", compare_string, _netmask_)
           # change to values 
           static_unique_string = "%(_ipaddress_)s/%(_netmask_)s@%(_hostname_)s:static_from_%(_fromzonename_)s@%(_ruleunique_)s"
           _ruleunique_ = "%(_natrulename_)s:%(_natrulesetname_)s" % {"_natrulename_":_natrulename_, "_natrulesetname_":_natrulesetname_}
           _destaddress_string_ = static_unique_string % {"_ipaddress_":_destaddress_, "_hostname_":_hostname_, "_fromzonename_":_fromzonename_, "_netmask_":_netmask_, "_ruleunique_":_ruleunique_}
           _hostaddress_string_ = static_unique_string % {"_ipaddress_":_hostaddress_, "_hostname_":_hostname_, "_fromzonename_":_fromzonename_, "_netmask_":_netmask_, "_ruleunique_":_ruleunique_}
           # 
           keyname_string_pattern = "%(_ipaddrvalue_)s/%(_netmask_)s"
           keyname_string = keyname_string_pattern % {"_netmask_":_netmask_,"_ipaddrvalue_":_destaddress_}
           insert_values = _hostaddress_string_
           natcache_memory = fillvalues_withkeyname(keyname_string, natcache_memory, insert_values)
           #
           keyname_string = keyname_string_pattern % {"_netmask_":_netmask_,"_ipaddrvalue_":_hostaddress_}
           insert_values = _destaddress_string_
           natcache_memory = fillvalues_withkeyname(keyname_string, natcache_memory, insert_values)
        # save cache file
        savethefile_dictvalueinput(_filename_, natcache_memory)
      if re.search(".nat.source.rule", _filename_, re.I):
        sourcepool_filename = _filename_.strip().split(".nat.source.rule")[0] + ".nat.source.pool"
        read_contents = readfile_getcontents(sourcepool_filename)
        #
        natcache_memory = {}
        pattern_start = "Pool name[ \t\n\r\f\v]+:"
        pattern_end = "Address range"
        start_end_linenumber_list = start_end_parse_from_string(read_contents, pattern_start, pattern_end)
        sourcepool_memory = getsourcepoolmember_info(start_end_linenumber_list, read_contents)
        # start processing source rule
        read_contents = readfile_getcontents(_filename_)
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
           [_natrulename_, _natrulesetname_, _fromzonename_, _tozonename_, _action_] = ["unknown", "unknown", "unknown", "unknown", "unknown"]
           # analysis each line of the one items
           for _msg_string_ in selective_list:
              compare_string = _msg_string_.strip()
              [_natrulename_, _natrulesetname_] = rule_information("source NAT rule:", compare_string, _natrulename_, _natrulesetname_)
              _fromzonename_ = lineanaysis_getlast_value("From zone[ \t\n\r\f\v]+:", compare_string, _fromzonename_)
              _tozonename_ = lineanaysis_getlast_value("To zone[ \t\n\r\f\v]+:", compare_string, _tozonename_)
              _action_ = lineanaysis_getlast_value("Action[ \t\n\r\f\v]+:", compare_string, _action_)
           # 
           _ruleunique_ = "%(_natrulename_)s:%(_natrulesetname_)s" % {"_natrulename_":_natrulename_, "_natrulesetname_":_natrulesetname_}
           source_unique_string = "%(_ipaddress_)s/%(_netmask_)s@%(_hostname_)s:source_from_%(_fromzonename_)s_to_%(_tozonename_)s@%(_ruleunique_)s"
           #
           natcache_memory = fillvalues_sourceinfo_withkeyname(_sourceipvaluelist_, sourcepool_memory[_action_], natcache_memory, str("32"), _hostname_, _fromzonename_, _tozonename_, _ruleunique_, source_unique_string)
           natcache_memory = fillvalues_sourceinfo_withkeyname(sourcepool_memory[_action_], _sourceipvaluelist_, natcache_memory, str("32"), _hostname_, _fromzonename_, _tozonename_, _ruleunique_, source_unique_string)
        #
        savethefile_dictvalueinput(_filename_, natcache_memory)
   # thread timeout 
   time.sleep(1)

def viewer_information():

   filenames_list = os.listdir(USER_VAR_CHCHES)
   updated_filestatus = {}
   filestatus = False
   for _filename_ in filenames_list:
      searched_element = re.search("cachenat_",_filename_,re.I)
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


           start_time = time.time()
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

           # delete file which name is cachenat_
           finish_time = time.time()
           spentabs_time = abs(float(finish_time) - float(start_time))
           for _dirctname_ in [USER_VAR_CHCHES]:
              for _filename_ in os.listdir(_dirctname_):
                 filename_direct = str(_dirctname_.strip() + _filename_.strip())
                 if re.search("cachenat_", filename_direct, re.I):
                   timeabs_value = abs(float(finish_time) - float(os.path.getctime(filename_direct)))
                   if timeabs_value > spentabs_time:
                     remove_cmd = "rm -rf %(filename_direct)s" % {"filename_direct":filename_direct}
                     os.popen(remove_cmd)

           # return
           return Response(viewer_information())

      except:
        message = "Post Algorithm has some problem!"
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

