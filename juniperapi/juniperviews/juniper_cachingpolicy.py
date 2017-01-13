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
   [searched_policyname, searched_policyaction, searched_sequencenumber, searched_fromzone, searched_tozone] = ["unknown", "unknown", "unknown", "unknown", "unknown"]
   for _string_line_ in everypolicy_group:
      searched_value = re.search(r"Policy: ([a-zA-Z0-9_\-:;\.]+)[,]+ action-type: ([a-zA-Z0-9_\-:;\.]+)[,]+", _string_line_.strip(), re.I)
      if searched_value:
        searched_policyname = searched_value.group(1)
        searched_policyaction = searched_value.group(2)
        continue
      searched_value = re.search(r"Sequence number: ([0-9]+)", _string_line_.strip(), re.I)
      if searched_value:
        searched_sequencenumber = searched_value.group(1)
        continue
      searched_value = re.search(r"From zone: ([a-zA-Z0-9_\-:;\.]+)[,] To zone: ([a-zA-Z0-9_\-:;\.]+)", _string_line_.strip(), re.I) 
      if searched_value:
        searched_fromzone = searched_value.group(1)
        searched_tozone = searched_value.group(2)
        continue
   return (searched_policyname, searched_policyaction, searched_sequencenumber, searched_fromzone, searched_tozone)


def insertcache_withkeyname(_expected_value_, source_cache_dict, _mylocation_, _sourcenetip_inthis_policy_):
   if _expected_value_ not in source_cache_dict.keys():
     source_cache_dict[_expected_value_] = []
   if _mylocation_ not in source_cache_dict[_expected_value_]:
     source_cache_dict[_expected_value_].append(_mylocation_)
   if unicode(_expected_value_) not in _sourcenetip_inthis_policy_:
     _sourcenetip_inthis_policy_.append(unicode(_expected_value_))
   return source_cache_dict, _sourcenetip_inthis_policy_



def getipnetvalues_from_paragraph(_policy_info_list_, _start_pattern_, _end_pattern_, source_cache_dict, policy_detail_cache_dict, policy_unique_name, _mylocation_, _policydetail_inner_keyname_):
   _sourcenetip_inthis_policy_ = []
   _searched_startend_ = start_end_parse_from_string(_policy_info_list_, _start_pattern_, _end_pattern_)
   for _start_end_ in _searched_startend_:
      _searched_linelist_ = _policy_info_list_[_start_end_[0]+int(1):_start_end_[-1]]
      for _eachline_ in _searched_linelist_:
         _expected_value_ = str(_eachline_.strip().split()[-1]).strip()
         source_cache_dict, _sourcenetip_inthis_policy_ = insertcache_withkeyname(_expected_value_, source_cache_dict, _mylocation_, _sourcenetip_inthis_policy_)
   policy_detail_cache_dict[unicode(policy_unique_name)][unicode(_policydetail_inner_keyname_)] = _sourcenetip_inthis_policy_
   return policy_detail_cache_dict, source_cache_dict


def zerozero_serviceport(sourceportvalue):
   if re.match("0-0", sourceportvalue, re.I):
     sourceportvalue = "0-65535"
   return sourceportvalue


def gettcpudpvalues_from_paragraph(_policy_info_list_,_start_pattern_,_end_pattern_,service_src_cache_dict,service_dst_cache_dict,policy_detail_cache_dict,policy_unique_name,_mylocation_):
   _srcapplication_inthis_policy_ = []
   _dstapplication_inthis_policy_ = []
   _searched_startend_ = start_end_parse_from_string(_policy_info_list_, _start_pattern_, _end_pattern_)
   for _start_end_ in _searched_startend_:
      _searched_linelist_ = _policy_info_list_[_start_end_[0]-int(1):_start_end_[-1]+int(1)]
      # 
      ipproto = str(re.search("IP protocol:[ \t\n\r\f\v]+([a-zA-Z0-9]+)[,]+", _searched_linelist_[0], re.I).group(1))
      sourceportvalue = str(re.search(_start_pattern_, _searched_linelist_[1], re.I).group(1))
      sourceportvalue = zerozero_serviceport(sourceportvalue)
      destinationvalue = str(re.search(_end_pattern_, _searched_linelist_[2], re.I).group(1))
      destinationvalue = zerozero_serviceport(destinationvalue)
      #
      sourceservice = "%(ipproto)s/%(portvalue)s" % {"ipproto":ipproto, "portvalue":sourceportvalue}
      destinationservice = "%(ipproto)s/%(portvalue)s" % {"ipproto":ipproto, "portvalue":destinationvalue}
      #
      service_src_cache_dict, _srcapplication_inthis_policy_ = insertcache_withkeyname(sourceservice, service_src_cache_dict, _mylocation_, _srcapplication_inthis_policy_) 
      service_dst_cache_dict, _dstapplication_inthis_policy_ = insertcache_withkeyname(destinationservice, service_dst_cache_dict, _mylocation_, _dstapplication_inthis_policy_) 
   #
   policy_detail_cache_dict[unicode(policy_unique_name)][unicode("source_application")] = _srcapplication_inthis_policy_
   policy_detail_cache_dict[unicode(policy_unique_name)][unicode("destination_application")] = _dstapplication_inthis_policy_
   return policy_detail_cache_dict, service_src_cache_dict, service_dst_cache_dict


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
   
   # the reason why network_pattern like this, IPv6 ::/0 or :/0   
   network_pattern = r"[0-9:]+/[0-9]+"
   pattern_start = r"^Policy: "
   pattern_end = r"Session log:"
   policy_group_start_end_list = start_end_parse_from_string(string_sum_content,pattern_start,pattern_end)
   #
   source_cache_dict = {}
   destination_cache_dict = {}
   service_src_cache_dict = {}
   service_dst_cache_dict = {}
   #
   policy_detail_cache_dict = {}
   #
   for _policy_start_end_ in policy_group_start_end_list:

      # this is policy info in the group
      _policy_info_list_ = string_sum_content[_policy_start_end_[0]:_policy_start_end_[-1]+int(1)]
      ( _policyname_, _policyaction_status_, _sequence_number_, _policyfromzone_, _policytozone_ ) = findout_policyname_sequence(_policy_info_list_) 

      # 
      _mylocation_ = "%(_policyname_)s:%(_sequence_number_)s" % {"_sequence_number_":_sequence_number_,"_policyname_":_policyname_}
      policy_unique_name = "%(_mylocation_)s@%(_filename_pattern_)s" % {"_mylocation_":str(_mylocation_),"_filename_pattern_":str(_filename_pattern_)}
      if unicode(policy_unique_name) not in policy_detail_cache_dict.keys():
        policy_detail_cache_dict[unicode(policy_unique_name)] = {}
        policy_detail_cache_dict[unicode(policy_unique_name)][unicode("source")] = []
        policy_detail_cache_dict[unicode(policy_unique_name)][unicode("destination")] = []
        policy_detail_cache_dict[unicode(policy_unique_name)][unicode("source_application")] = []
        policy_detail_cache_dict[unicode(policy_unique_name)][unicode("destination_application")] = []
        policy_detail_cache_dict[unicode(policy_unique_name)][unicode("action")] = "unknown"
      policy_detail_cache_dict[unicode(policy_unique_name)][unicode("action")] = _policyaction_status_

      # source and destination caching processing
      policy_detail_cache_dict,source_cache_dict=getipnetvalues_from_paragraph(_policy_info_list_,"Source addresses:","Destination addresses:",source_cache_dict,policy_detail_cache_dict,policy_unique_name,_mylocation_,"source") 
      policy_detail_cache_dict,destination_cache_dict=getipnetvalues_from_paragraph(_policy_info_list_,"Destination addresses:","Application:",destination_cache_dict,policy_detail_cache_dict,policy_unique_name,_mylocation_,"destination")

      # application "tcp" and "udp"
      policy_detail_cache_dict, service_src_cache_dict, service_dst_cache_dict = gettcpudpvalues_from_paragraph(_policy_info_list_,"Source port range:[ \t\n\r\f\v]+\[([a-zA-Z0-9]+\-[a-zA-Z0-9]+)\]","Destination port range:[ \t\n\r\f\v]+\[([a-zA-Z0-9]+\-[a-zA-Z0-9]+)\]",service_src_cache_dict,service_dst_cache_dict,policy_detail_cache_dict,policy_unique_name,_mylocation_)


      # extra application protocol
      for _string_inside_ in _policy_info_list_:
         # icmp
         if re.search("IP protocol: icmp", _string_inside_.strip(), re.I):

           service_src_cache_dict, policy_detail_cache_dict[unicode(policy_unique_name)][unicode("source_application")] = insertcache_withkeyname("icmp", service_src_cache_dict, _mylocation_, policy_detail_cache_dict[unicode(policy_unique_name)][unicode("source_application")])
           service_dst_cache_dict, policy_detail_cache_dict[unicode(policy_unique_name)][unicode("destination_application")] = insertcache_withkeyname("icmp", service_dst_cache_dict, _mylocation_, policy_detail_cache_dict[unicode(policy_unique_name)][unicode("destination_application")])

      

 
      # application service_cache_dict = {}
      #_srcapplication_inthis_policy_ = []
      #_dstapplication_inthis_policy_ = []
      #_start_pattern_ = "Application:"
      #_end_pattern_ = ["Destination port range:","code="]

      #_searched_startend_ = start_end_parse_from_string_endlist(_policy_info_list_,_start_pattern_,_end_pattern_)
      #for _start_end_ in _searched_startend_:

      #   _searched_linelist_ = _policy_info_list_[_start_end_[0]:_start_end_[-1]+int(1)]
      #   # protocol infomation
      #   # there is three type of any 
      #   # 1. 0/0-0     : any/0-0 or any/0-65535
      #   # 2. tcp/0-0   : tcp/0-0 or tcp/0-65535
      #   # 3. udp/0-0   : udp/0-0 or udp/0-65535
      #   # protocol, alg, timeout
      #   _ipprotocol_ = "0"
      #   _algvalue_ = "0"
      #   _prototimeout_ = "3600"
      #   _protoalgtimeout_string_ = "%(_ipprotocol_)s:%(_algvalue_)s:%(_prototimeout_)s" % {"_ipprotocol_":_ipprotocol_, "_algvalue_":_algvalue_, "_prototimeout_":_prototimeout_}

      #   for _eachline_ in _searched_linelist_:
      #      # protocol, alg, timeout  
      #      protocolstatus_pattern = r"IP protocol: ([a-zA-Z0-9_\-:;\.]+)[,] ALG: ([a-zA-Z0-9_\-:;\.]+)[,] Inactivity timeout: ([a-zA-Z0-9_\-:;\.]+)"
      #      searching_content = re.search(protocolstatus_pattern, str(_eachline_), re.I)
      #      if searching_content:
      #        _ipprotocol_ = searching_content.group(1).lower()
      #        _algvalue_ = searching_content.group(2).lower()
      #        _prototimeout_ = searching_content.group(3).lower()
      #        # proto alg time name
      #        _protoalgtimeout_string_ = "%(_ipprotocol_)s:%(_algvalue_)s:%(_prototimeout_)s" % {"_ipprotocol_":_ipprotocol_, "_algvalue_":_algvalue_, "_prototimeout_":_prototimeout_}

      #      # source application
      #      sourceport_pattern = r"Source port range: \[([0-9]+\-[0-9]+)\]"
      #      searching_content = re.search(sourceport_pattern, str(_eachline_), re.I)
      #      if searching_content:
      #        _port_range_value_ = searching_content.group(1)
      #        any_application_pattern = r"0-0"
      #        anysearching_content = re.search(any_application_pattern, _port_range_value_, re.I)
      #        if anysearching_content:
      #          _port_range_value_ = str("0-65535")
      #        _application_string_ = "%(_proto_)s/%(_srv_number_)s" % {"_proto_":str(_ipprotocol_),"_srv_number_":str(_port_range_value_)}
      #        if str(_application_string_) not in service_src_cache_dict.keys():
      #          service_src_cache_dict[str(_application_string_)] = []
      #        if _mylocation_ not in service_src_cache_dict[str(_application_string_)]:
      #          service_src_cache_dict[str(_application_string_)].append(_mylocation_)
      #        _policyapp_unique_keyname_ = "%(_protoalgtimeout_string_)s:%(_port_range_value_)s" % {"_protoalgtimeout_string_":_protoalgtimeout_string_,"_port_range_value_":_port_range_value_}
      #        if unicode(_policyapp_unique_keyname_) not in _srcapplication_inthis_policy_:
      #          _srcapplication_inthis_policy_.append(unicode(_policyapp_unique_keyname_))

      #      # destination application
      #      destination_pattern = "Destination port range: \[([0-9]+\-[0-9]+)\]"
      #      searching_content = re.search(destination_pattern, str(_eachline_), re.I)
      #      if searching_content:
      #        _port_range_value_ = searching_content.group(1)
      #        any_application_pattern = r"0-0"
      #        anysearching_content = re.search(any_application_pattern, _port_range_value_, re.I)
      #        if anysearching_content:
      #          _port_range_value_ = str("0-65535")  
      #        _application_string_ = "%(_proto_)s/%(_srv_number_)s" % {"_proto_":str(_ipprotocol_),"_srv_number_":str(_port_range_value_)}
      #        if str(_application_string_) not in service_dst_cache_dict.keys():
      #          service_dst_cache_dict[str(_application_string_)] = []
      #        if _mylocation_ not in service_dst_cache_dict[str(_application_string_)]:              
      #          service_dst_cache_dict[str(_application_string_)].append(_mylocation_)
      #        _policyapp_unique_keyname_ = "%(_protoalgtimeout_string_)s:%(_port_range_value_)s" % {"_protoalgtimeout_string_":_protoalgtimeout_string_,"_port_range_value_":_port_range_value_}
      #        if unicode(_policyapp_unique_keyname_) not in _dstapplication_inthis_policy_:
      #          _dstapplication_inthis_policy_.append(unicode(_policyapp_unique_keyname_))

      #      # icmp case : source and destination
      #      icmp_string_pattern = r"ICMP Information: type=([a-zA-Z0-9_\-:;\.]+)[,] code=([a-zA-Z0-9_\-:;\.]+)"
      #      searching_content = re.search(icmp_string_pattern, str(_eachline_), re.I)
      #      if searching_content:
      #        #_application_string_ = "%(_proto_)s/%(_srv_number_)s" % {"_proto_":str(_ipprotocol_),"_srv_number_":str("0-65535")}
      #        _application_string_ = "%(_proto_)s" % {"_proto_":str(_ipprotocol_)}
      #        _icmptype_ = searching_content.group(1)
      #        _icmpcode_ = searching_content.group(2)
      #        icmp_unique_keyname = "%(_protoalgtimeout_string_)s:%(_icmptype_)s:%(_icmpcode_)s" % {"_protoalgtimeout_string_":_protoalgtimeout_string_,"_icmptype_":_icmptype_,"_icmpcode_":_icmpcode_}
      #        # source add
      #        if str(_application_string_) not in service_src_cache_dict.keys():
      #          service_src_cache_dict[str(_application_string_)] = []
      #        if _mylocation_ not in service_src_cache_dict[str(_application_string_)]:
      #          service_src_cache_dict[str(_application_string_)].append(_mylocation_)
      #        if unicode(icmp_unique_keyname) not in _srcapplication_inthis_policy_:
      #          _srcapplication_inthis_policy_.append(unicode(icmp_unique_keyname))
      #        # destination add 
      #        if str(_application_string_) not in service_dst_cache_dict.keys():
      #          service_dst_cache_dict[str(_application_string_)] = []
      #        if _mylocation_ not in service_dst_cache_dict[str(_application_string_)]:
      #          service_dst_cache_dict[str(_application_string_)].append(_mylocation_)
      #        if unicode(icmp_unique_keyname) not in _dstapplication_inthis_policy_:
      #          _dstapplication_inthis_policy_.append(unicode(icmp_unique_keyname))
      #
      #policy_detail_cache_dict[unicode(policy_unique_name)][unicode("source_application")] = _srcapplication_inthis_policy_
      #policy_detail_cache_dict[unicode(policy_unique_name)][unicode("destination_application")] = _dstapplication_inthis_policy_


   cache_dictbox = {}
   cache_dictbox["source"] = source_cache_dict
   cache_dictbox["destination"] = destination_cache_dict
   cache_dictbox["source_application"] = service_src_cache_dict
   cache_dictbox["destination_application"] = service_dst_cache_dict 
   cache_dictbox["policydetail"] = policy_detail_cache_dict

   # file write
   filename_string = "cachepolicy_%(_filename_pattern_)s.txt" % {"_filename_pattern_":str(_filename_pattern_).strip()} 
   JUNIPER_DEVICELIST_DBFILE = USER_VAR_CHCHES + filename_string
   f = open(JUNIPER_DEVICELIST_DBFILE,"w")
   f.write(json.dumps(cache_dictbox))
   f.close()
   #print "processing %(_counter_)s completed!" % {"_counter_":str(filename_string)}  
   # timeout 
   time.sleep(1)
      

def caching_policy(_ipaddress_,_hostname_):
   # 
   filestring_pattern = "%(_hostname_)s@%(_ipaddress_)s" % {"_ipaddress_":_ipaddress_,"_hostname_":_hostname_}
   pattern_fromtozone = "from_([a-zA-Z0-9\_\-]+)_to_([a-zA-Z0-9\_\-]+)_start"
   filenames_list_indirectory = os.listdir(USER_VAR_POLICIES)
   filename_category_toread = []
   for _filename_ in filenames_list_indirectory:
      if re.search(filestring_pattern, str(_filename_), re.I):
        searched_string = re.search(pattern_fromtozone,str(_filename_),re.I)
        _from_zonename_ = searched_string.group(1)
        _to_zonename_ = searched_string.group(2)
        pattern_readstring = "%(_hostname_)s@%(_ipaddress_)s_from_%(_from_zonename_)s_to_%(_to_zonename_)s" % {"_to_zonename_":_to_zonename_,"_from_zonename_":_from_zonename_,"_ipaddress_":_ipaddress_,"_hostname_":_hostname_}
        if pattern_readstring not in filename_category_toread:
          filename_category_toread.append(pattern_readstring)
   # caching 
   for _filename_pattern_ in filename_category_toread:
      run_caching(_filename_pattern_)

   #_threads_ = []
   #for _filename_pattern_ in filename_category_toread:      
   #   th = threading.Thread(target=run_caching, args=(_filename_pattern_,))
   #   th.start()
   #   _threads_.append(th)
   #for th in _threads_:
   #   th.join()   

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
def juniper_cachingpolicy(request,format=None):

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

           #_threads_ = []
           #for _ipaddress_ in valid_access_ip:
           #   th = threading.Thread(target=caching_policy, args=(_ipaddress_,ip_device_dict[_ipaddress_],))
           #   th.start()
           #   _threads_.append(th)
           #for th in _threads_:
           #   th.join()

           _processor_list_ = []
           for _accessip_ in valid_access_ip:
              _processor_ = Process(target = caching_policy, args = (_accessip_, ip_device_dict[_accessip_],))
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
                 if re.search("cachepolicy_", filename_direct, re.I):
                   timeabs_value = abs(float(finish_time) - float(os.path.getctime(filename_direct)))
                   if timeabs_value > spentabs_time:
                     remove_cmd = "rm -rf %(filename_direct)s" % {"filename_direct":filename_direct}
                     os.popen(remove_cmd)

           # return
           return Response(viewer_information())

      except:
        message = "Post Algorithm has some problem!"
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

