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
from juniperapi.setting import USER_VAR_CHCHES
from juniperapi.setting import PYTHON_MULTI_PROCESS
from juniperapi.setting import PYTHON_MULTI_THREAD

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


def search_hadevice_string(_routing_dict_,_ipaddress_):
   return_string = "none"
   for _dataDict_ in _routing_dict_:
      for _hadeviceip_ in _dataDict_[u"hadevicesip"]:
         if re.search(str(_ipaddress_),str(_hadeviceip_),re.I):
           return_string = "%(_devicename_)s@%(_deviceip_)s" % {"_devicename_":_dataDict_[u"devicehostname"],"_deviceip_":_dataDict_[u"apiaccessip"]} 
           break
   if re.search(return_string,"none",re.I):
     return Response(["error, routing table has issue!"], status=status.HTTP_400_BAD_REQUEST)
   return return_string


def parsing_filename_to_data(_routing_dict_,_src_string_):
   parsed_src_string = str(_src_string_).strip().split("@")
   if len(parsed_src_string) != int(2):
     return Response("error, input info is not proper format!", status=status.HTTP_400_BAD_REQUEST)
   [ parsed_routing_netip, parsed_device ] = parsed_src_string

   ipaddress_pattern = "[0-9]+.[0-9]+.[0-9]+.[0-9]+/[0-9]+:[0-9]+.[0-9]+.[0-9]+.[0-9]+/[0-9]+"
   if not re.search(ipaddress_pattern,str(parsed_routing_netip),re.I):
     return Response("error, route format is not proper format!", status=status.HTTP_400_BAD_REQUEST)
   parsed_routingnitip_string = parsed_routing_netip.strip().split(":")

   if len(parsed_routingnitip_string) != int(2):
     return Response("error, routing engin of input info is not proper format!", status=status.HTTP_400_BAD_REQUEST)
   [ input_policy_info, route_info ] = parsed_routingnitip_string

   parsed_device_string = parsed_device.strip().split(":")
   if len(parsed_device_string) != int(3):
     return Response("error, device part of input info is not proper format!", status=status.HTTP_400_BAD_REQUEST)
   [ device_name, device_ip, zonename ] = parsed_device_string
   deviceandip_string = search_hadevice_string(_routing_dict_, device_ip) 
   return [ str(input_policy_info), deviceandip_string, zonename ] 

def get_listvalue_matchedby_keyname(file_database,input_netip):
   return_values = []
   if unicode(input_netip) in file_database:
     return_values = file_database[unicode(input_netip)]
   elif str(input_netip) in file_database:
     return_values = file_database[str(input_netip)]
   return return_values


def compare_srcdstapplist(srclist,dstlist,srcapplist,dstapplist):
   set_srclist = set(srclist)
   set_dstlist = set(dstlist)
   compare_srcdst = set_srclist.intersection(dstlist)
   compare_dstsrc = set_dstlist.intersection(srclist)   
   set_srcapplist = set(srcapplist)
   set_dstapplist = set(dstapplist)
   compare_srcdstapp = set_srcapplist.intersection(dstapplist)
   compare_dstsrcapp = set_dstapplist.intersection(srcapplist)
   compare_final_srcdst = compare_srcdst.intersection(compare_srcdstapp)
   compare_final_dstsrc = compare_dstsrc.intersection(compare_dstsrcapp)   
   if (compare_srcdst != compare_dstsrc) or (compare_srcdstapp != compare_dstsrcapp) or (compare_final_srcdst != compare_final_dstsrc):
     return Response("error, application compare has issue!", status=status.HTTP_400_BAD_REQUEST)    
   templist_box = []
   for _common_ in list(compare_final_srcdst):  
      if str(_common_) not in templist_box:
        templist_box.append(str(_common_))
   return templist_box


def compare_including_netip(file_database,inputsrc_netip):
   return_matched_list = []
   inputsrc_netip_ipnetwork = IPNetwork(unicode(inputsrc_netip))
   inputsrc_netip_subnet = str(str(inputsrc_netip).strip().split("/")[-1])
   keyname_netip = file_database.keys()
   for _netip_ in keyname_netip:
      _netip_ipnetwork_ = IPNetwork(unicode(_netip_))
      _netip_subnet_ =  str(str(_netip_).strip().split("/")[-1])
      if int(_netip_subnet_) <= int(inputsrc_netip_subnet):
        if inputsrc_netip_ipnetwork in _netip_ipnetwork_:
          return_matched_list = return_matched_list + file_database[_netip_]
   return return_matched_list

def partial_includ_match_netip(file_database,inputsrc_netip):
   return_matched_list = []
   inputsrc_netip_ipnetwork = IPNetwork(unicode(inputsrc_netip))
   inputsrc_netip_subnet = str(str(inputsrc_netip).strip().split("/")[-1])
   keyname_netip = file_database.keys()
   for _netip_ in keyname_netip:
      _netip_ipnetwork_ = IPNetwork(unicode(_netip_))
      _netip_subnet_ =  str(str(_netip_).strip().split("/")[-1])
      if int(_netip_subnet_) <= int(inputsrc_netip_subnet):
        if inputsrc_netip_ipnetwork in _netip_ipnetwork_:
          return_matched_list = return_matched_list + file_database[_netip_]
      else:
        if _netip_ipnetwork_ in inputsrc_netip_ipnetwork:
          return_matched_list = return_matched_list + file_database[_netip_] 
   return return_matched_list


def compare_including_application(file_database,input_application):
   #
   application_split = input_application.strip().split("/")
   #
   any_app_matching = re.search(r"any", str(application_split[0].strip().lower()), re.I)
   interger_any_app_matching = re.search(r"0", str(application_split[0].strip().lower()), re.I)
   tcp_app_matching = re.search(r"tcp", str(application_split[0].strip().lower()), re.I)
   udp_app_matching = re.search(r"udp", str(application_split[0].strip().lower()), re.I)
   icmp_app_matching = re.search(r"icmp", str(application_split[0].strip().lower()), re.I) 
   #
   #if re.search(r"tcp", application_split[0].strip().lower(), re.I) or re.search(r"udp", application_split[0].strip().lower(), re.I):
   if any_app_matching or interger_any_app_matching or tcp_app_matching or udp_app_matching:
     [ _proto_, _port_range_ ] = application_split   
     portrange_split = _port_range_.strip().split("-") 
     [ _start_port_, _end_port_ ] = portrange_split 
   else:
     if icmp_app_matching:
       if unicode(r"icmp") in file_database.keys():
         return file_database[unicode(r"icmp")]
   # tcp udp processing
   return_matched_list = [] 
   _keyname_database_ = file_database.keys()
   for _keyname_ in _keyname_database_:    
      #
      _stringkeyname_values_ = str(_keyname_)
      #
      _any_app_match_ = re.search(r"any", _stringkeyname_values_.lower(), re.I)
      _interger_any_app_match_ = re.search(r"0", _stringkeyname_values_.lower(), re.I)
      _tcp_app_match_ = re.search(r"tcp", _stringkeyname_values_.lower(), re.I)
      _udp_app_match_ = re.search(r"udp", _stringkeyname_values_.lower(), re.I)
      _icmp_app_match_ = re.search(r"icmp", _stringkeyname_values_.lower(), re.I) 
      # 
      #if re.search(r"tcp", str(_keyname_), re.I) or re.search(r"udp", str(_keyname_), re.I):
      if _any_app_match_ or _interger_any_app_match_ or _tcp_app_match_ or _udp_app_match_:
        key_split = _keyname_.strip().split("/")
        [ _key_proto_, _key_port_range_ ] = key_split
        keyport_split = _key_port_range_.strip().split("-")
        [ _key_start_port_, _key_end_port_ ] = keyport_split
        if re.match(str(_proto_).lower(),str(_key_proto_).lower(),re.I):
          keyportragne_list = range(int(_key_start_port_),int(_key_end_port_)+int(1))
          portragne_list = range(int(_start_port_),int(_end_port_)+int(1))
          if len(portragne_list) <= len(keyportragne_list):
            if set(portragne_list).intersection(keyportragne_list) == set(portragne_list):
              return_matched_list = return_matched_list + file_database[_keyname_]
      else:
        #if re.search(r"icmp", str(_keyname_), re.I):
        if _icmp_app_match_:
          continue
   return return_matched_list            
    
def partial_including_application(file_database,input_application):
   #
   application_split = input_application.strip().split("/")
   #
   any_app_matching = re.search(r"any", str(application_split[0].strip().lower()), re.I)
   interger_any_app_matching = re.search(r"0", str(application_split[0].strip().lower()), re.I)
   tcp_app_matching = re.search(r"tcp", str(application_split[0].strip().lower()), re.I)
   udp_app_matching = re.search(r"udp", str(application_split[0].strip().lower()), re.I)
   icmp_app_matching = re.search(r"icmp", str(application_split[0].strip().lower()), re.I)
   #
   if any_app_matching or interger_any_app_matching or tcp_app_matching or udp_app_matching:
   #if re.search(r"tcp", application_split[0].strip().lower(), re.I) or re.search(r"udp", application_split[0].strip().lower(), re.I):
     [ _proto_, _port_range_ ] = application_split
     portrange_split = _port_range_.strip().split("-")
     [ _start_port_, _end_port_ ] = portrange_split
   else:
     #if re.search(r"icmp", application_split[0].strip().lower(), re.I):
     if icmp_app_matching:
       return file_database[unicode(r"icmp")]
   # tcp udp processing
   return_matched_list = []
   _keyname_database_ = file_database.keys()
   for _keyname_ in _keyname_database_:    
      #
      _stringkeyname_values_ = str(_keyname_)
      #
      _any_app_match_ = re.search(r"any", _stringkeyname_values_.lower(), re.I)
      _interger_any_app_match_ = re.search(r"0", _stringkeyname_values_.lower(), re.I)
      _tcp_app_match_ = re.search(r"tcp", _stringkeyname_values_.lower(), re.I)
      _udp_app_match_ = re.search(r"udp", _stringkeyname_values_.lower(), re.I)
      _icmp_app_match_ = re.search(r"icmp", _stringkeyname_values_.lower(), re.I)             
      # 
      #if re.search(r"tcp", str(_keyname_), re.I) or re.search(r"udp", str(_keyname_), re.I):
      if _any_app_match_ or _interger_any_app_match_ or _tcp_app_match_ or _udp_app_match_:
        key_split = _keyname_.strip().split("/")
        [ _key_proto_, _key_port_range_ ] = key_split    
        keyport_split = _key_port_range_.strip().split("-")
        [ _key_start_port_, _key_end_port_ ] = keyport_split
        if re.match(str(_proto_).lower(),str(_key_proto_).lower(),re.I):
          keyportragne_list = range(int(_key_start_port_),int(_key_end_port_)+int(1))
          portragne_list = range(int(_start_port_),int(_end_port_)+int(1))
          if len(portragne_list) <= len(keyportragne_list):
            if set(portragne_list).intersection(keyportragne_list) == set(portragne_list):
              return_matched_list = return_matched_list + file_database[_keyname_]
          else:
            if set(portragne_list).intersection(keyportragne_list) == set(keyportragne_list):
              return_matched_list = return_matched_list + file_database[_keyname_]
      else:
        #if re.search(r"icmp", str(_keyname_), re.I):
        if _icmp_app_match_:
          continue
   return return_matched_list

def perfect_match_lookup_function(srcnetip_file_database, dstnetip_file_database, srcapp_file_database, dstapp_file_database, inputsrc_netip, inputdst_netip, src_proto_port_string, dst_proto_port_string):
   perfect_matched_policylist = []
   source_in_filedb_list = []
   destination_in_filedb_list = []
   application_in_filedb_list = []
   source_in_filedb_list  = get_listvalue_matchedby_keyname(srcnetip_file_database, inputsrc_netip)
   destination_in_filedb_list  = get_listvalue_matchedby_keyname(dstnetip_file_database, inputdst_netip)
   src_application_in_filedb_list = get_listvalue_matchedby_keyname(srcapp_file_database, src_proto_port_string)
   dst_application_in_filedb_list = get_listvalue_matchedby_keyname(dstapp_file_database, dst_proto_port_string)
   matched_policylist = []
   if len(source_in_filedb_list)*len(destination_in_filedb_list)*len(src_application_in_filedb_list)*len(dst_application_in_filedb_list):
     matched_policylist = compare_srcdstapplist(source_in_filedb_list,destination_in_filedb_list,src_application_in_filedb_list,dst_application_in_filedb_list)
   return matched_policylist    

def include_match_lookup_function(srcnetip_file_database, dstnetip_file_database, srcapp_file_database, dstapp_file_database, inputsrc_netip, inputdst_netip, src_proto_port_string, dst_proto_port_string):
   included_matched_policylist = []
   source_in_filedb_list = []
   destination_in_filedb_list = []
   application_in_filedb_list = []
   source_in_filedb_list = compare_including_netip(srcnetip_file_database, inputsrc_netip)
   destination_in_filedb_list = compare_including_netip(dstnetip_file_database, inputdst_netip)
   src_application_in_filedb_list = compare_including_application(srcapp_file_database, src_proto_port_string)
   dst_application_in_filedb_list = compare_including_application(dstapp_file_database, dst_proto_port_string)
   matched_policylist = []
   if len(source_in_filedb_list)*len(destination_in_filedb_list)*len(src_application_in_filedb_list)*len(dst_application_in_filedb_list):
     matched_policylist = compare_srcdstapplist(source_in_filedb_list,destination_in_filedb_list,src_application_in_filedb_list,dst_application_in_filedb_list)
   return matched_policylist    

def patial_match_lookup_function(srcnetip_file_database, dstnetip_file_database, srcapp_file_database, dstapp_file_database, inputsrc_netip, inputdst_netip, src_proto_port_string, dst_proto_port_string):
   source_in_filedb_list = []
   destination_in_filedb_list = []
   application_in_filedb_list = []
   source_in_filedb_list = partial_includ_match_netip(srcnetip_file_database, inputsrc_netip)
   destination_in_filedb_list = partial_includ_match_netip(dstnetip_file_database, inputdst_netip)
   src_application_in_filedb_list = partial_including_application(srcapp_file_database, src_proto_port_string)
   dst_application_in_filedb_list = partial_including_application(dstapp_file_database, dst_proto_port_string)
   matched_policylist = []
   if len(source_in_filedb_list)*len(destination_in_filedb_list)*len(src_application_in_filedb_list)*len(dst_application_in_filedb_list):
     matched_policylist = compare_srcdstapplist(source_in_filedb_list,destination_in_filedb_list,src_application_in_filedb_list,dst_application_in_filedb_list)
   return matched_policylist    


def findout_policydetail_from_cache(_rulename_list_, device_fromtozone_string, file_database):
   policy_detail = {}
   for _rulename_string_ in _rulename_list_:
      if unicode(_rulename_string_) not in policy_detail.keys():
        unique_string_name = "%(_rulename_string_)s@%(device_fromtozone_string)s" % {"_rulename_string_":str(_rulename_string_), "device_fromtozone_string":str(device_fromtozone_string)}
        policy_detail[unicode(_rulename_string_)] = file_database[unicode(unique_string_name)] 
   return policy_detail
      

def procesing_searchingmatching(_each_processorData_, this_processor_queue):

   for parameter_combination in _each_processorData_:
      [ inputsrc_netip, inputsrc_device, inputsrc_zone, inputdst_netip, inputdst_device, inputdst_zone, _app_value_, cache_filename ] = parameter_combination 
      string_Dictvalues = {"inputsrc_netip":str(inputsrc_netip), "inputsrc_device":str(inputsrc_device), "inputsrc_zone":str(inputsrc_zone), "inputdst_netip":str(inputdst_netip), "inputdst_device":str(inputdst_device), "inputdst_zone":str(inputdst_zone)}

      if re.match(inputsrc_device, inputdst_device, re.I):
        policy_cache_filename = "cachepolicy_%(inputsrc_device)s_from_%(inputsrc_zone)s_to_%(inputdst_zone)s.txt" % string_Dictvalues
        device_fromtozone_string = "%(inputsrc_device)s_from_%(inputsrc_zone)s_to_%(inputdst_zone)s" % string_Dictvalues

        if (str(policy_cache_filename) in cache_filename) or (unicode(policy_cache_filename) in cache_filename):
          # database file read
          database_filefull = USER_VAR_CHCHES + policy_cache_filename
          f = open(database_filefull,"r")
          string_contents = f.readlines()
          f.close()
          stream = BytesIO(string_contents[0])
          file_database = JSONParser().parse(stream) 
          #
          tempdict_box = {}
          tempdict_box[u'sourceip'] = str(inputsrc_netip)
          tempdict_box[u'destinationip'] = str(inputdst_netip)
          tempdict_box[u'devicename'] = str(inputsrc_device)
          tempdict_box[u'fromzone'] = str(inputsrc_zone)
          tempdict_box[u'tozone'] = str(inputdst_zone)
          tempdict_box[u'matchedpolicy'] = {}
          tempdict_box[u'matchedpolicy'][u'perfectmatch'] = []
          tempdict_box[u'matchedpolicy'][u'includematch'] = []
          tempdict_box[u'matchedpolicy'][u'partialmatch'] = []
          tempdict_box[u'matchedpolicydetail'] = {}
          tempdict_box[u'matchedpolicydetail'][u'perfectmatch'] = {}
          tempdict_box[u'matchedpolicydetail'][u'includematch'] = {}
          tempdict_box[u'matchedpolicydetail'][u'partialmatch'] = {}

          # 
          appvalue_string = _app_value_.strip().split("/")
          # match the what kind of the protocol is required!
          any_app_matching = re.search(r"any", str(appvalue_string[0].strip().lower()), re.I)
          interger_any_app_matching = re.search(r"0", str(appvalue_string[0].strip().lower()), re.I)
          tcp_app_matching = re.search(r"tcp", str(appvalue_string[0].strip().lower()), re.I)
          udp_app_matching = re.search(r"udp", str(appvalue_string[0].strip().lower()), re.I)
          icmp_app_matching = re.search(r"icmp", str(appvalue_string[0].strip().lower()), re.I)
          # 
          if tcp_app_matching or udp_app_matching or any_app_matching or interger_any_app_matching:
            [ _app_proto_, _app_number_ ] = appvalue_string
            [ _src_portrange_, _dst_portrange_ ] = _app_number_.strip().split(":")
            tempdict_box[u'protocoltype'] = str(_app_proto_)
            tempdict_box[u'sourceportrange'] = str(_src_portrange_)
            tempdict_box[u'destinationportrange'] = str(_dst_portrange_)
            src_proto_port_string = "%(_proto_)s/%(_portrange_)s" % {"_proto_":str(_app_proto_),"_portrange_":str(tempdict_box[u'sourceportrange'])}
            dst_proto_port_string = "%(_proto_)s/%(_portrange_)s" % {"_proto_":str(_app_proto_),"_portrange_":str(tempdict_box[u'destinationportrange'])}
          else:
            if icmp_app_matching:
              _app_proto_  = appvalue_string[0]
              tempdict_box[u'protocoltype'] = str(_app_proto_)
              tempdict_box[u'sourceportrange'] = str("none")
              tempdict_box[u'destinationportrange'] = str("none")
              src_proto_port_string = "%(_proto_)s" % {"_proto_":str(_app_proto_)}
              dst_proto_port_string = "%(_proto_)s" % {"_proto_":str(_app_proto_)}
          # perfect matching processing
          matched_policylist = perfect_match_lookup_function(file_database[u'source'], file_database[u'destination'], file_database[u'source_application'], file_database[u'destination_application'], inputsrc_netip, inputdst_netip, src_proto_port_string, dst_proto_port_string)
          #tempdict_box[u'matchedpolicy'][u'perfectmatch'] = tempdict_box[u'matchedpolicy'][u'perfectmatch'] + matched_policylist
          tempdict_box[u'matchedpolicy'][u'perfectmatch'] = matched_policylist
          tempdict_box[u'matchedpolicydetail'][u'perfectmatch'] = findout_policydetail_from_cache(tempdict_box[u'matchedpolicy'][u'perfectmatch'], device_fromtozone_string, file_database[u'policydetail'])
          perfect_matched_policylist = copy.copy(tempdict_box[u'matchedpolicy'][u'perfectmatch'])

          # include matching processing
          matched_policylist = include_match_lookup_function(file_database[u'source'], file_database[u'destination'], file_database[u'source_application'], file_database[u'destination_application'], inputsrc_netip, inputdst_netip, src_proto_port_string, dst_proto_port_string)
          for _matcheditem_ in matched_policylist:
             if _matcheditem_ not in perfect_matched_policylist:
               tempdict_box[u'matchedpolicy'][u'includematch'].append(_matcheditem_)
          tempdict_box[u'matchedpolicydetail'][u'includematch'] = findout_policydetail_from_cache(tempdict_box[u'matchedpolicy'][u'includematch'], device_fromtozone_string, file_database[u'policydetail'])
          included_matched_policylist = copy.copy(tempdict_box[u'matchedpolicy'][u'includematch'])

          # patial matching processing
          matched_policylist = patial_match_lookup_function(file_database[u'source'], file_database[u'destination'], file_database[u'source_application'], file_database[u'destination_application'], inputsrc_netip, inputdst_netip, src_proto_port_string, dst_proto_port_string)
          for _matcheditem_ in matched_policylist:
             if (_matcheditem_ not in perfect_matched_policylist) and (_matcheditem_ not in included_matched_policylist):
               tempdict_box[u'matchedpolicy'][u'partialmatch'].append(_matcheditem_)
          tempdict_box[u'matchedpolicydetail'][u'partialmatch'] = findout_policydetail_from_cache(tempdict_box[u'matchedpolicy'][u'partialmatch'], device_fromtozone_string, file_database[u'policydetail'])

          # insert the queue
          this_processor_queue.put(tempdict_box)
 
   print "processor is completed....!"
   time.sleep(0)


@api_view(['GET','POST'])
@csrf_exempt
def juniper_searchpolicy(request,format=None):

   # 
   global tatalsearched_values, threadlock_key
   threadlock_key = threading.Lock()
   tatalsearched_values = []

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
             "application" : "icmp"
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
        cache_filename = os.listdir(USER_VAR_CHCHES)

        # get devicelist
        CURL_command = "curl http://0.0.0.0:"+RUNSERVER_PORT+"/juniper/devicelist/"
        get_info = os.popen(CURL_command).read().strip()
        stream = BytesIO(get_info)
        _routing_dict_ = JSONParser().parse(stream)

        CURL_command = "curl -H \"Accept: application/json\" -X POST -d \'"+json.dumps(_input_)+"\' http://0.0.0.0:"+RUNSERVER_PORT+"/juniper/searchzonefromroute/"
        get_info = os.popen(CURL_command).read().strip()
        stream = BytesIO(get_info)
        data_from_CURL_command = JSONParser().parse(stream)

        #
        every_parameter_combination_list = []
        for _dictData_ in data_from_CURL_command:
           for _src_string_ in _dictData_[u"sourceip"]:
              [ inputsrc_netip, inputsrc_device, inputsrc_zone ] = parsing_filename_to_data(_routing_dict_,_src_string_)
              for _dst_value_ in _dictData_[u"destinationip"]:
                 [ inputdst_netip, inputdst_device, inputdst_zone ] = parsing_filename_to_data(_routing_dict_,_dst_value_)
                 if re.match(inputsrc_device, inputdst_device, re.I):
                   for _app_value_ in _dictData_[u"application"]:
                      parameter_combination = [ inputsrc_netip, inputsrc_device, inputsrc_zone, inputdst_netip, inputdst_device, inputdst_zone, _app_value_, cache_filename ]
                      every_parameter_combination_list.append(parameter_combination)
        # init 
        processing_combination = []
        processing_queue = []
        if len(every_parameter_combination_list) <= int(PYTHON_MULTI_PROCESS): 
          for _i_ in range(len(every_parameter_combination_list)):
             processing_combination.append([])
             processing_queue.append(Queue(maxsize=0))
        else:
          for _i_ in range(int(PYTHON_MULTI_PROCESS)):
             processing_combination.append([])
             processing_queue.append(Queue(maxsize=0))
        #
        print "Total number of Data : %(_tnumber_)s.... planned with queues for the processing...." % {"_tnumber_":str(len(processing_combination))}
        count = 0
        for parameter_combination in every_parameter_combination_list:
           (_values_, _last_) = divmod(count, int(int(PYTHON_MULTI_PROCESS)))
           processing_combination[_last_].append(parameter_combination)
           count = count + 1   
        print "datas are divied..!"
        #
        count = 0
        _processor_list_ = []
        for _each_processorData_ in processing_combination:
           this_processor_queue = processing_queue[count]
           _processor_ = Process(target = procesing_searchingmatching, args = (_each_processorData_, this_processor_queue,)) 
           _processor_.start()
           _processor_list_.append(_processor_) 
           count = count + 1 
        for _processor_ in _processor_list_:
           _processor_.join()
        #
        search_result = [] 
        for _queue_ in processing_queue:
           while not _queue_.empty():
                search_result.append(_queue_.get())
        #
        return Response(search_result)

      except:
        message = "Post Algorithm has some problem!"
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

