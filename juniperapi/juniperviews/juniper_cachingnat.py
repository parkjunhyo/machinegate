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

def findout_policyname_sequence(everypolicy_group):
   # default init values
   _policyname_status_ = False
   _policysequence_status_ = False
   _policyzone_status_ = False  
   # common pattern :([a-zA-Z0-9,_\-:;\.]+)
   policyname_spattern = r"Policy: ([a-zA-Z0-9_\-:;\.]+)[,] action-type: ([a-zA-Z0-9_\-:;\.]+)"
   policysequence_spattern = r"Sequence number: ([0-9]+)"
   policyzone_spattern = r"From zone: ([a-zA-Z0-9_\-:;\.]+)[,] To zone: ([a-zA-Z0-9_\-:;\.]+)"
   # init values
   searched_policyname = "none"
   _policyaction_status_ = "deny"
   searched_sequencenumber = "none"
   searched_from = "none"
   searched_to = "none"
   # processing
   for _string_line_ in everypolicy_group:
      if not (_policyname_status_ and _policysequence_status_ and _policyzone_status_):
        # policy name and status
        searching_content = re.search(str(policyname_spattern), str(_string_line_), re.I)
        if searching_content:
          _policyname_status_ = True
          searched_policyname = searching_content.group(1)
          _policyaction_status_ = searching_content.group(2)
        # sequece number 
        searching_content = re.search(policysequence_spattern, str(_string_line_), re.I)
        if searching_content:
          _policysequence_status_ = True   
          searched_sequencenumber = searching_content.group(1) 
        # from to zone name  
        searching_content = re.search(policyzone_spattern, str(_string_line_), re.I) 
        if searching_content:
          _policyzone_status_ = True
          searched_from = searching_content.group(1)
          searched_to = searching_content.group(2)
   # return
   return (searched_policyname, _policyaction_status_, searched_sequencenumber, searched_from, searched_to)



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

        pattern_start = "Static NAT rule:"
        pattern_end = "Number of sessions[ \t\n\r\f\v]+:"
      #
        f = open(_filename_, "r")
        read_contents = f.readlines()
        f.close()
        start_end_linenumber_list = start_end_parse_from_string(read_contents, pattern_start, pattern_end)

        static_cache_dict = {}
        for index_list in start_end_linenumber_list:
           selective_list = read_contents[index_list[0]:index_list[-1]+int(1)]

           #
           _natrulename_ = "unknown"
           _natrulesetname_ = "unknown"
           _fromzonename_ = "unknown"
           _destaddress_ = "unknown"
           _hostaddress_ = "unknown"
           _netmask_ = "unknown"
           #
           
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

           #  
           _destaddress_string_ = "%(_destaddress_)s/%(_netmask_)s@%(_hostname_)s:static_from_%(_fromzonename_)s" % {"_destaddress_":_destaddress_, "_hostname_":_hostname_, "_fromzonename_":_fromzonename_, "_netmask_":_netmask_}
           _hostaddress_string_ = "%(_hostaddress_)s/%(_netmask_)s@%(_hostname_)s:static_from_%(_fromzonename_)s" % {"_hostaddress_":_hostaddress_, "_hostname_":_hostname_, "_fromzonename_":_fromzonename_, "_netmask_":_netmask_}

           #
           _keyname_ = "%(_destaddress_)s/%(_netmask_)s" % {"_destaddress_":_destaddress_, "_netmask_":_netmask_}
           if _keyname_ not in static_cache_dict.keys():
             static_cache_dict[_keyname_] = {}
             static_cache_dict[_keyname_][u"rulename"] = []
             static_cache_dict[_keyname_][u"rulesetname"] = []
             static_cache_dict[_keyname_][u"changeto"] = []

           if _natrulename_ not in static_cache_dict[_keyname_][u"rulename"]:
             static_cache_dict[_keyname_][u"rulename"].append(_natrulename_)
 
           if _natrulesetname_ not in static_cache_dict[_keyname_][u"rulesetname"]:
             static_cache_dict[_keyname_][u"rulesetname"].append(_natrulesetname_)

           if _hostaddress_string_ not in static_cache_dict[_keyname_][u"changeto"]:
             static_cache_dict[_keyname_][u"changeto"].append(_hostaddress_string_)


           _keyname_ = "%(_hostaddress_)s/%(_netmask_)s" % {"_hostaddress_":_hostaddress_, "_netmask_":_netmask_}
           if _keyname_ not in static_cache_dict.keys():
             static_cache_dict[_keyname_] = {}
             static_cache_dict[_keyname_][u"rulename"] = []
             static_cache_dict[_keyname_][u"rulesetname"] = []
             static_cache_dict[_keyname_][u"changeto"] = []

           if _natrulename_ not in static_cache_dict[_keyname_][u"rulename"]:
             static_cache_dict[_keyname_][u"rulename"].append(_natrulename_)

           if _natrulesetname_ not in static_cache_dict[_keyname_][u"rulesetname"]:
             static_cache_dict[_keyname_][u"rulesetname"].append(_natrulesetname_)

           if _destaddress_string_ not in static_cache_dict[_keyname_][u"changeto"]:
             static_cache_dict[_keyname_][u"changeto"].append(_destaddress_string_)

        print static_cache_dict

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

           #_threads_ = []
           #for _ipaddress_ in valid_access_ip:
           #   th = threading.Thread(target=caching_policy, args=(_ipaddress_,ip_device_dict[_ipaddress_],))
           #   th.start()
           #   _threads_.append(th)
           #for th in _threads_:
           #   th.join()

           # return
           return Response(viewer_information())

      except:
        message = "Post Algorithm has some problem!"
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

