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
from juniperapi.setting import USER_VAR_POLICIES 
from juniperapi.setting import PYTHON_MULTI_PROCESS

import os,re,copy,json,time,threading,sys,random
import paramiko
from netaddr import *
from multiprocessing import Process, Queue, Lock

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

def ipnet_values_obtain(everypolicy_group, startstringpattern, endstringpattern):
   # pattern
   network_address_pattern = r"([0-9]+.[0-9]+.[0-9]+.[0-9]+/[0-9]+)"
   searched_matched_values = []
   for start_end_list in start_end_parse_from_string(everypolicy_group, startstringpattern, endstringpattern):
      processed_group = everypolicy_group[int(start_end_list[0]):int(start_end_list[-1])]
      for _processed_string_line_ in processed_group:
         searched_status = re.search(network_address_pattern, str(_processed_string_line_), re.I)
         if searched_status:
           searched_networkaddress_value = searched_status.group(1)
           if unicode(searched_networkaddress_value) not in searched_matched_values:
             searched_matched_values.append(unicode(searched_networkaddress_value))
   return searched_matched_values

def application_values_obtain(everypolicy_group, startstringpattern, endstringpattern):
   # pattern
   protocolstatus_pattern = r"IP protocol: ([a-zA-Z0-9]+), ALG: ([a-zA-Z0-9]+), Inactivity timeout: ([a-zA-Z0-9]+)"
   sourceport_pattern = "Source port range: \[([0-9]+\-[0-9]+)\]"
   destination_pattern = "Destination port range: \[([0-9]+\-[0-9]+)\]"
   # initstatus
   searched_matched_values = []
   for start_end_list in start_end_parse_from_string_endlist(everypolicy_group, startstringpattern, endstringpattern):
      processed_group = everypolicy_group[int(start_end_list[0]):(int(start_end_list[-1])+int(1))]
      # init each value
      protoproperty = ""
      sourceportrange = ""
      destinationportrange = ""
      for _processed_string_line_ in processed_group:
         searched_status = re.search(protocolstatus_pattern, str(_processed_string_line_), re.I)
         if searched_status:
           protoproperty = "%(proto)s:%(alg)s:%(timeout)s" % {"proto":str(searched_status.group(1)),"alg":str(searched_status.group(2)),"timeout":str(searched_status.group(3))}
         searched_status = re.search(sourceport_pattern, str(_processed_string_line_), re.I)
         if searched_status:
           sourceportrange = str(searched_status.group(1))
         searched_status = re.search(destination_pattern, str(_processed_string_line_), re.I)
         if searched_status:
           destinationportrange = str(searched_status.group(1))

      if len(protoproperty) * len(sourceportrange) * len(destinationportrange):
        port_string = "%(protoproperty)s@S%(sourceportrange)s:D%(destinationportrange)s" % {"protoproperty":protoproperty,"sourceportrange":sourceportrange,"destinationportrange":destinationportrange}
        if unicode(port_string) not in searched_matched_values:
          searched_matched_values.append(unicode(port_string))
      else:
        continue
   return searched_matched_values

def policydetail_obtain(in_devicename, in_destinationip, in_src_application, in_dst_application, in_fromzone, in_tozone, in_proto_application, in_sourceip, policies_filename, using_deviceinfo_values, policymatch_status, in_matchedpolicy, file_contents_lists, policyname_seqnumber):

   # thread parameter initailization
   global tatalsearched_values, threadlock_key

   # policy name and sequence number
   [ _policyname_, _sequencenumber_ ] = str(policyname_seqnumber).strip().split(":")

   # policy group parsing
   pattern_start = r"^Policy: "
   pattern_end = r"Session log:"
   for _start_end_combination_ in start_end_parse_from_string(file_contents_lists, pattern_start, pattern_end):

      everypolicy_group = file_contents_lists[int(_start_end_combination_[0]):int(_start_end_combination_[-1])]
      # confirm this policy group validation 
      _policyname_status_ = False
      _policysequence_status_ = False
      _policyzone_status_ = False  
      _policyaction_status_ = "deny"
      policyname_pattern = "Policy: %(_policyname_)s, action-type: ([a-zA-Z0-9]+)," % {"_policyname_":str(_policyname_)}
      policysequence_pattern = "Sequence number: %(_sequencenumber_)s" % {"_sequencenumber_":str(_sequencenumber_)}
      policyzone_pattern = "From zone: %(in_fromzone)s, To zone: %(in_tozone)s" % {"in_fromzone":str(in_fromzone), "in_tozone":str(in_tozone)}
      for _string_line_ in everypolicy_group:
         if not (_policyname_status_ and _policysequence_status_ and _policyzone_status_):
           searching_content = re.search(policyname_pattern, str(_string_line_), re.I)
           if searching_content:
             _policyname_status_ = True
             _policyaction_status_ = searching_content.group(1)
           if re.search(policysequence_pattern, str(_string_line_), re.I):
             _policysequence_status_ = True
           if re.search(policyzone_pattern, str(_string_line_), re.I):
             _policyzone_status_ = True 

      # this is processing only  
      if _policyname_status_ and _policysequence_status_ and _policyzone_status_:
        tempDict_box = {}
        tempDict_box[u'devicename'] = unicode(in_devicename)
        tempDict_box[u'policyname'] = unicode(_policyname_)
        tempDict_box[u'policysequencenumber'] = unicode(_sequencenumber_)
        tempDict_box[u'fromzone'] = unicode(in_fromzone)
        tempDict_box[u'tozone'] = unicode(in_tozone)
        tempDict_box[u'policymatchstatus'] = unicode(policymatch_status)
        tempDict_box[u'policyactionstatus'] = unicode(_policyaction_status_)
        unique_keyDict_values = { 
                                  "policyname":tempDict_box[u'policyname'],
                                  "policysequencenumber":tempDict_box[u'policysequencenumber'],
                                  "devicename":tempDict_box[u'devicename'],
                                  "fromzone":tempDict_box[u'fromzone'],
                                  "tozone":tempDict_box[u'tozone'],
                                  "policymatchstatus":tempDict_box[u'policymatchstatus']
                                }

        # unique policy key name creation
        unique_keyname = "%(policyname)s:%(policysequencenumber)s_%(devicename)s_%(fromzone)s:%(tozone)s_%(policymatchstatus)s" % unique_keyDict_values

        # pattern
        network_address_pattern = r"([0-9]+.[0-9]+.[0-9]+.[0-9]+/[0-9]+)"

        searched_source_values = ipnet_values_obtain(everypolicy_group, "Source addresses:", "Destination addresses:")
        searched_destination_values = ipnet_values_obtain(everypolicy_group, "Destination addresses:", "Application:")
        searched_application_values = application_values_obtain(everypolicy_group, "Application:", ["Destination port range:", "code="])

        tempDict_box[u'sourcenetip'] = unicode(searched_source_values)
        tempDict_box[u'destinationnetip'] = unicode(searched_destination_values)
        tempDict_box[u'applcations'] = unicode(searched_application_values)
 
        # fill default container
        threadlock_key.acquire()
        if unicode(unique_keyname) not in tatalsearched_values.keys():
          tatalsearched_values[unicode(unique_keyname)] = {}
          tatalsearched_values[unicode(unique_keyname)] = tempDict_box
        threadlock_key.release()
      else:
        continue
   # threading waiting
   time.sleep(0)

def findout_rule_from_policiesdatabase(in_devicename, in_destinationip, in_src_application, in_dst_application, in_fromzone, in_tozone, in_proto_application, in_matchedpolicy, in_sourceip, policies_filename, using_deviceinfo_values, file_contents_lists, policymatch_status):

   for _rulename_seqno_ in in_matchedpolicy[unicode(policymatch_status)]:
      policyname_seqnumber = str(_rulename_seqno_)
      policydetail_obtain(in_devicename, in_destinationip, in_src_application, in_dst_application, in_fromzone, in_tozone, in_proto_application, in_sourceip, policies_filename, using_deviceinfo_values, policymatch_status, in_matchedpolicy, file_contents_lists, policyname_seqnumber)

   # thread time out
   time.sleep(0)

def calculation_for_dividing( listData, divNumber ):
   ( _div_value_, _mod_value_ ) = divmod(int(len(listData)),int(divNumber))
   element_count = int(0)
   if _mod_value_ == int(0):
     element_count = int(_div_value_)
   else:
     element_count = int(_div_value_) + int(1)
   return element_count

def run_each_processor(_dictData_list_, process_lock, process_queues, policies_filename, using_deviceinfo_values):

   global tatalsearched_values, threadlock_key
   tatalsearched_values = {}
   threadlock_key = threading.Lock()

   _threadlist_ = []

   for _dictData_values_ in _dictData_list_:

      # initailizaed values
      in_devicename = _dictData_values_[u"devicename"]
      in_destinationip = _dictData_values_[u"destinationip"]
      in_src_application = _dictData_values_[u"src_application"]
      in_dst_application = _dictData_values_[u"dst_application"]
      in_fromzone = _dictData_values_[u"fromzone"]
      in_tozone = _dictData_values_[u"tozone"]
      in_proto_application = _dictData_values_[u"proto_application"]
      in_matchedpolicy = _dictData_values_[u"matchedpolicy"]
      in_sourceip = _dictData_values_[u"sourceip"]

      # every file read
      filename_pattern = "%(_devicename_)s_from_%(_fromzone_)s_to_%(_tozone_)s" % {"_devicename_":str(in_devicename), "_fromzone_":str(in_fromzone), "_tozone_":str(in_tozone)}
      file_contents_lists = []
      for _filefrom_ in policies_filename:
         if re.search(str(filename_pattern),str(_filefrom_),re.I):
           fullfilename = USER_VAR_POLICIES + str(_filefrom_)
           f = open(fullfilename,"r")
           read_contents = f.readlines()
           f.close()
           file_contents_lists = file_contents_lists + read_contents

      # 
      in_matchedpolicy_keynameslist = in_matchedpolicy.keys()
      for _keyname_ in in_matchedpolicy_keynameslist:
         policymatch_status = str(_keyname_)
         _thread_ = threading.Thread( target = findout_rule_from_policiesdatabase, args = (in_devicename, in_destinationip, in_src_application, in_dst_application, in_fromzone, in_tozone, in_proto_application, in_matchedpolicy, in_sourceip, policies_filename, using_deviceinfo_values, file_contents_lists, policymatch_status,) )
         _thread_.start()
         _threadlist_.append(_thread_)

   # finishing
   for _thread_ in _threadlist_:
      _thread_.join()
   #
   process_lock.acquire()
   process_common_values = process_queues.get()
   # sum dictionay   
   tatalsearched_values_keyname = tatalsearched_values.keys()
   process_common_values_keyname = process_common_values.keys()
   for _keyname_ in tatalsearched_values_keyname:
     if (unicode(_keyname_) not in process_common_values_keyname) or (str(_keyname_) not in process_common_values_keyname):
       process_common_values[unicode(_keyname_)] = {}
       process_common_values[unicode(_keyname_)] = tatalsearched_values[_keyname_]
   process_queues.put(process_common_values)
   process_lock.release()
   #
   time.sleep(0)

@api_view(['GET','POST'])
@csrf_exempt
def juniper_searchpolicy_tools_whereismyrule(request,format=None):

   # get method
   if request.method == 'GET':
      try:
         get_message = [
           {
             "sourceip" : "172.22.113.10/32;172.22.113.11/32",
             "destinationip" : "172.22.208.15/32",
             "application" : "tcp/0-0:1700-1700;<protocol>/<souce port range>:<destination port range>"
           },
           {
             "sourceip" : "172.22.0.0/16",
             "destinationip" : "172.22.209.0/24",
             "application" : "icmp/0-0:0-65535"
           },
           {
             "sourceip" : "172.22.112.0/23",
             "destinationip" : "172.22.208.10/28",
             "application" : "any/0-0:0-0;tcp/0-0:0-0;udp/0-65535:0-65535"
           }
         ]
         return Response(get_message)
      except:
         message = ["device list database is not existed!"]
         return Response(message, status=status.HTTP_400_BAD_REQUEST)


   elif request.method == 'POST':

      try:

        # input
        _input_ = JSONParser().parse(request)

        # cache directory
        policies_filename = os.listdir(USER_VAR_POLICIES)

        # device information
        CURL_command = "curl http://0.0.0.0:"+RUNSERVER_PORT+"/juniper/devicelist/"
        get_info = os.popen(CURL_command).read().strip()
        stream = BytesIO(get_info)
        deviceinfo_from_command = JSONParser().parse(stream)
        using_deviceinfo_values = {} 
        for _dictData_values_ in deviceinfo_from_command:
           if unicode(_dictData_values_[u"devicehostname"]) not in using_deviceinfo_values.keys():
             using_deviceinfo_values[unicode(_dictData_values_[u"devicehostname"])] = {}
             using_deviceinfo_values[unicode(_dictData_values_[u"devicehostname"])][u"apiaccessip"] = unicode(_dictData_values_[u"apiaccessip"])
             using_deviceinfo_values[unicode(_dictData_values_[u"devicehostname"])][u"mgmtip"] = unicode(_dictData_values_[u"mgmtip"])
             using_deviceinfo_values[unicode(_dictData_values_[u"devicehostname"])][u"failover"] = unicode(_dictData_values_[u"failover"])

        # get the matched and searched policy
        CURL_command = "curl -H \"Accept: application/json\" -X POST -d \'"+json.dumps(_input_)+"\' http://0.0.0.0:"+RUNSERVER_PORT+"/juniper/searchpolicy/"
        get_info = os.popen(CURL_command).read().strip()
        stream = BytesIO(get_info)
        data_from_CURL_command = JSONParser().parse(stream)

        # multiple processing : process_lock, process_queues
        process_lock = Lock()
        process_queues = Queue()
        process_common_values = {}
        process_queues.put(process_common_values)

        # processing number and seperate the data
        each_element_number = calculation_for_dividing( data_from_CURL_command, int(PYTHON_MULTI_PROCESS) )
        processing_number = calculation_for_dividing( data_from_CURL_command, int(each_element_number))
        dividedData_list = []
        for _ivalue_ in range(int(processing_number)):
           expected_begin_index = int(_ivalue_) * each_element_number
           expected_last_index = (int(_ivalue_) + 1) * each_element_number
           if len(data_from_CURL_command) < int(expected_last_index):
             expected_last_index = len(data_from_CURL_command)
           dividedData_list.append(data_from_CURL_command[expected_begin_index:expected_last_index])

        # run processing : run_each_processor(dividedData_list, process_lock, process_queues, policies_filename, using_deviceinfo_values)
        _multiprocess_ = []
        for _dictData_list_ in dividedData_list:
           _processor_ = Process( target = run_each_processor, args=(_dictData_list_, process_lock, process_queues, policies_filename, using_deviceinfo_values,) )
           _processor_.start()
           _multiprocess_.append(_processor_)
        for _processor_ in _multiprocess_:
           _processor_.join() 

        # thread finish : read and transfer global value 
        everysum_from_each_process = process_queues.get()
        return Response(everysum_from_each_process.values())

      except:
        message = "Post Algorithm has some problem!"
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

