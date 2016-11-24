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
from juniperapi.setting import USER_VAR_CHCHES

import os,re,copy,json,time,threading,sys
import paramiko

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

def run_caching(_filename_pattern_):
   matched_filenames_list = []
   filenames_list_indirectory = os.listdir(USER_VAR_POLICIES)
   for _filename_ in filenames_list_indirectory:
      if re.search(_filename_pattern_,str(_filename_),re.I):
        if str(_filename_) not in matched_filenames_list:
          matched_filenames_list.append(str(_filename_))

   string_sum_content = []
   for _matched_filename_ in matched_filenames_list:
      _filepath_ = USER_VAR_POLICIES + _matched_filename_
      f = open(_filepath_,"r")
      string_content = f.readlines()
      f.close()
      string_sum_content = string_sum_content + string_content
      

   network_pattern = r"[0-9:]+/[0-9]+"
   pattern_start = r"^Policy: "
   pattern_end = r"Session log:"
   policy_group_start_end_list = start_end_parse_from_string(string_sum_content,pattern_start,pattern_end)
   #
   source_cache_dict = {}
   destination_cache_dict = {}
   service_cache_dict = {}
   #
   for _policy_start_end_ in policy_group_start_end_list:
      # policy name
      _policyname_ = str(str(str(string_sum_content[_policy_start_end_[0]]).strip().split("Policy: ")[1]).strip().split(",")[0])
      # each policy group
      _policy_info_list_ = string_sum_content[_policy_start_end_[0]:_policy_start_end_[-1]]
      # sequence number : Sequence number:
      _sequence_number_ = "none"
      for _eachline_ in _policy_info_list_:
         if re.search(r"Sequence number:",str(_eachline_),re.I):
           _sequence_number_ = str(_eachline_.strip().split()[-1])
           break
      _mylocation_ = "%(_policyname_)s:%(_sequence_number_)s" % {"_sequence_number_":_sequence_number_,"_policyname_":_policyname_}
      # source
      _start_pattern_ = "Source addresses:"
      _end_pattern_ = "Destination addresses:"
      _searched_startend_ = start_end_parse_from_string(_policy_info_list_,_start_pattern_,_end_pattern_)
      for _start_end_ in _searched_startend_:
         _searched_linelist_ = _policy_info_list_[_start_end_[0]:_start_end_[-1]]
         for _eachline_ in _searched_linelist_:
            _expected_value_ = str(_eachline_.strip().split()[-1])
            if re.search(network_pattern,_expected_value_,re.I):
              if str(_expected_value_) not in source_cache_dict.keys():
                source_cache_dict[str(_expected_value_)] = []
              source_cache_dict[str(_expected_value_)].append(_mylocation_)

      # destination
      _start_pattern_ = "Destination addresses:" 
      _end_pattern_ = "Application:"
      _searched_startend_ = start_end_parse_from_string(_policy_info_list_,_start_pattern_,_end_pattern_)
      for _start_end_ in _searched_startend_:
         _searched_linelist_ = _policy_info_list_[_start_end_[0]:_start_end_[-1]]
         for _eachline_ in _searched_linelist_:
            _expected_value_ = str(_eachline_.strip().split()[-1])
            if re.search(network_pattern,_expected_value_,re.I):
              if str(_expected_value_) not in destination_cache_dict.keys():
                destination_cache_dict[str(_expected_value_)] = []
              destination_cache_dict[str(_expected_value_)].append(_mylocation_)


      # application service_cache_dict = {}
      _start_pattern_ = "Application:"
      _end_pattern_ = "Destination port range:"
      _searched_startend_ = start_end_parse_from_string(_policy_info_list_,_start_pattern_,_end_pattern_)
      for _start_end_ in _searched_startend_:
         _searched_linelist_ = _policy_info_list_[_start_end_[0]:_start_end_[-1]+int(1)]
 
         for _eachline_ in _searched_linelist_:
            _dest_service_pattern_ = "Destination port range: "
            if re.search(_dest_service_pattern_,str(_eachline_),re.I):

              _expected_search_ = re.search("([0-9]+)\-([0-9]+)",str(_eachline_))
              _start_number_ = int(_expected_search_.group(1))
              _end_number_ = int(_expected_search_.group(2))

              for _range_number_ in range(_end_number_-_start_number_+1):
                 _srv_number_ = _range_number_ + _start_number_
                 if str(_srv_number_) not in service_cache_dict.keys():
                   service_cache_dict[str(_srv_number_)] = []
                 service_cache_dict[str(_srv_number_)].append(_mylocation_)
      
      

   cache_dictbox = {}
   cache_dictbox["source"] = source_cache_dict
   cache_dictbox["destination"] = destination_cache_dict
   cache_dictbox["application"] = service_cache_dict

   print _filename_pattern_
   # file write
   filename_string = "routingtable_%(_ipaddr_)s.txt" % {"_ipaddr_":devicemgmtip} 
   #JUNIPER_DEVICELIST_DBFILE = USER_VAR_CHCHES + filename_string
   #f = open(JUNIPER_DEVICELIST_DBFILE,"w")
   #f.write(json.dumps(return_all))
   #f.close()
    
   # timeout 
   time.sleep(1)
      

def caching_policy(_ipaddress_,_hostname_):
   # 
   filestring_pattern = "%(_hostname_)s@%(_ipaddress_)s" % {"_ipaddress_":_ipaddress_,"_hostname_":_hostname_}
   pattern_fromtozone = "from_([a-zA-Z0-9\_\-]+)_to_([a-zA-Z0-9\_\-]+)_start"
   filenames_list_indirectory = os.listdir(USER_VAR_POLICIES)
   filename_category_toread = []
   for _filename_ in filenames_list_indirectory:
      if re.search(filestring_pattern,str(_filename_),re.I):
        searched_string = re.search(pattern_fromtozone,str(_filename_),re.I)
        _from_zonename_ = searched_string.group(1)
        _to_zonename_ = searched_string.group(2)
        pattern_readstring = "%(_hostname_)s@%(_ipaddress_)s_from_%(_from_zonename_)s_to_%(_to_zonename_)s" % {"_to_zonename_":_to_zonename_,"_from_zonename_":_from_zonename_,"_ipaddress_":_ipaddress_,"_hostname_":_hostname_}
        if pattern_readstring not in filename_category_toread:
          filename_category_toread.append(pattern_readstring)
   # caching 
   _threads_ = []
   for _filename_pattern_ in filename_category_toread:      
      th = threading.Thread(target=run_caching, args=(_filename_pattern_,))
      th.start()
      _threads_.append(th)
   for th in _threads_:
      th.join()   

        


   # thread timeout 
   time.sleep(1)

def viewer_information():
   filenames_list = os.listdir(USER_VAR_POLICIES)
   updated_filestatus = {}
   filestatus = False
   for _filename_ in filenames_list:
      searched_element = re.search("([a-zA-Z0-9\_\-]+)@([0-9]+.[0-9]+.[0-9]+.[0-9]+)_[a-zA-Z0-9\_\-\. \t\n\r\f\v]+.policy",_filename_,re.I)
      if searched_element:
        filepath = USER_VAR_POLICIES + _filename_
        updated_filestatus[str(_filename_)] = str(time.ctime(os.path.getmtime(filepath)))
        filestatus = True

   if not filestatus:
     return ["error, export the policy!"] 

   return updated_filestatus 


@api_view(['GET','POST'])
@csrf_exempt
def juniper_cachingpolicy(request,format=None):

   JUNIPER_DEVICELIST_DBFILE = USER_DATABASES_DIR + "devicelist.txt"

   # get method
   if request.method == 'GET':
      try:

         return Response(viewer_information())

      except:
         message = ["device list database is not existed!"]
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

           _threads_ = []
           for _ipaddress_ in valid_access_ip:
              th = threading.Thread(target=caching_policy, args=(_ipaddress_,ip_device_dict[_ipaddress_],))
              th.start()
              _threads_.append(th)
           for th in _threads_:
              th.join()

           # return
           return Response(viewer_information())

      except:
        message = "Post Algorithm has some problem!"
        return Response(message, status=status.HTTP_400_BAD_REQUEST)
