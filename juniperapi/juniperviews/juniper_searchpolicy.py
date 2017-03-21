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
from juniperapi.setting import system_property

import os,re,copy,json,time,threading,sys,random
import paramiko
from netaddr import *
from multiprocessing import Process, Queue, Lock

from shared_function import obtainjson_from_mongodb as obtainjson_from_mongodb
from shared_function import exact_findout as exact_findout
from shared_function import findout_primary_devices as findout_primary_devices


class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders its content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)


def search_hadevice_string(_routing_dict_,_ipaddress_):
   return_string = "none@none"
   for _dataDict_ in _routing_dict_:
      for _hadeviceip_ in _dataDict_[u"hadevicesip"]:
         if re.search(str(_ipaddress_), str(_hadeviceip_), re.I):
           return_string = "%(_devicename_)s@%(_deviceip_)s" % {"_devicename_":_dataDict_[u"devicehostname"],"_deviceip_":_dataDict_[u"apiaccessip"]} 
           break
   return return_string


def parsing_filename_to_data(_routing_dict_,_src_string_):
   [ parsed_routing_netip, parsed_device ] = str(_src_string_).strip().split("@")
   [ device_name, device_ip, zonename ] = parsed_device.strip().split(":")
   deviceandip_string = search_hadevice_string(_routing_dict_, device_ip) 
   return [ str(parsed_routing_netip), deviceandip_string, zonename ] 

#def get_listvalue_matchedby_keyname(file_database,input_netip):
#   return_values = []
#   if unicode(input_netip) in file_database:
#     return_values = file_database[unicode(input_netip)]
#   elif str(input_netip) in file_database:
#     return_values = file_database[str(input_netip)]
#   return return_values


#def compare_srcdstapplist(srclist,dstlist,srcapplist,dstapplist):
#   set_srclist = set(srclist)
#   set_dstlist = set(dstlist)
#   compare_srcdst = set_srclist.intersection(dstlist)
#   compare_dstsrc = set_dstlist.intersection(srclist)   
#   set_srcapplist = set(srcapplist)
#   set_dstapplist = set(dstapplist)
#   compare_srcdstapp = set_srcapplist.intersection(dstapplist)
#   compare_dstsrcapp = set_dstapplist.intersection(srcapplist)
#   compare_final_srcdst = compare_srcdst.intersection(compare_srcdstapp)
#   compare_final_dstsrc = compare_dstsrc.intersection(compare_dstsrcapp)   
#   if (compare_srcdst != compare_dstsrc) or (compare_srcdstapp != compare_dstsrcapp) or (compare_final_srcdst != compare_final_dstsrc):
#     return Response("error, application compare has issue!", status=status.HTTP_400_BAD_REQUEST)    
#   templist_box = []
#   for _common_ in list(compare_final_srcdst):  
#      if str(_common_) not in templist_box:
#        templist_box.append(str(_common_))
#   return templist_box


#def compare_including_netip(file_database,inputsrc_netip):
#   return_matched_list = []
#   inputsrc_netip_ipnetwork = IPNetwork(unicode(inputsrc_netip))
#   inputsrc_netip_subnet = str(str(inputsrc_netip).strip().split("/")[-1])
#   keyname_netip = file_database.keys()
#   for _netip_ in keyname_netip:
#      _netip_ipnetwork_ = IPNetwork(unicode(_netip_))
#      _netip_subnet_ =  str(str(_netip_).strip().split("/")[-1])
#      if int(_netip_subnet_) <= int(inputsrc_netip_subnet):
#        if inputsrc_netip_ipnetwork in _netip_ipnetwork_:
#          return_matched_list = return_matched_list + file_database[_netip_]
#   return return_matched_list

#def partial_includ_match_netip(file_database,inputsrc_netip):
#   return_matched_list = []
#   inputsrc_netip_ipnetwork = IPNetwork(unicode(inputsrc_netip))
#   inputsrc_netip_subnet = str(str(inputsrc_netip).strip().split("/")[-1])
#   keyname_netip = file_database.keys()
#   for _netip_ in keyname_netip:
#      _netip_ipnetwork_ = IPNetwork(unicode(_netip_))
#      _netip_subnet_ =  str(str(_netip_).strip().split("/")[-1])
#      if int(_netip_subnet_) <= int(inputsrc_netip_subnet):
#        if inputsrc_netip_ipnetwork in _netip_ipnetwork_:
#          return_matched_list = return_matched_list + file_database[_netip_]
#      else:
#        if _netip_ipnetwork_ in inputsrc_netip_ipnetwork:
#          return_matched_list = return_matched_list + file_database[_netip_] 
#   return return_matched_list


#def compare_including_application(file_database,input_application):
#   #
#   application_split = input_application.strip().split("/")
#   #
#   any_app_matching = re.search(r"any", str(application_split[0].strip().lower()), re.I)
#   interger_any_app_matching = re.search(r"0", str(application_split[0].strip().lower()), re.I)
#   tcp_app_matching = re.search(r"tcp", str(application_split[0].strip().lower()), re.I)
#   udp_app_matching = re.search(r"udp", str(application_split[0].strip().lower()), re.I)
#   icmp_app_matching = re.search(r"icmp", str(application_split[0].strip().lower()), re.I) 
#   #
#   #if re.search(r"tcp", application_split[0].strip().lower(), re.I) or re.search(r"udp", application_split[0].strip().lower(), re.I):
#   if any_app_matching or interger_any_app_matching or tcp_app_matching or udp_app_matching:
#     [ _proto_, _port_range_ ] = application_split   
#     portrange_split = _port_range_.strip().split("-") 
#     [ _start_port_, _end_port_ ] = portrange_split 
#   else:
#     if icmp_app_matching:
#       if unicode(r"icmp") in file_database.keys():
#         return file_database[unicode(r"icmp")]
#   # tcp udp processing
#   return_matched_list = [] 
#   _keyname_database_ = file_database.keys()
#   for _keyname_ in _keyname_database_:    
#      #
#      _stringkeyname_values_ = str(_keyname_)
#      #
#      _any_app_match_ = re.search(r"any", _stringkeyname_values_.lower(), re.I)
#      _interger_any_app_match_ = re.search(r"0", _stringkeyname_values_.lower(), re.I)
#      _tcp_app_match_ = re.search(r"tcp", _stringkeyname_values_.lower(), re.I)
#      _udp_app_match_ = re.search(r"udp", _stringkeyname_values_.lower(), re.I)
#      _icmp_app_match_ = re.search(r"icmp", _stringkeyname_values_.lower(), re.I) 
#      # 
#      #if re.search(r"tcp", str(_keyname_), re.I) or re.search(r"udp", str(_keyname_), re.I):
#      if _any_app_match_ or _interger_any_app_match_ or _tcp_app_match_ or _udp_app_match_:
#        key_split = _keyname_.strip().split("/")
#        [ _key_proto_, _key_port_range_ ] = key_split
#        keyport_split = _key_port_range_.strip().split("-")
#        [ _key_start_port_, _key_end_port_ ] = keyport_split
#        if re.match(str(_proto_).lower(),str(_key_proto_).lower(),re.I):
#          keyportragne_list = range(int(_key_start_port_),int(_key_end_port_)+int(1))
#          portragne_list = range(int(_start_port_),int(_end_port_)+int(1))
#          if len(portragne_list) <= len(keyportragne_list):
#            if set(portragne_list).intersection(keyportragne_list) == set(portragne_list):
#              return_matched_list = return_matched_list + file_database[_keyname_]
#      else:
#        #if re.search(r"icmp", str(_keyname_), re.I):
#        if _icmp_app_match_:
#          continue
#   return return_matched_list            
    
#def partial_including_application(file_database,input_application):
#   #
#   application_split = input_application.strip().split("/")
#   #
#   any_app_matching = re.search(r"any", str(application_split[0].strip().lower()), re.I)
#   interger_any_app_matching = re.search(r"0", str(application_split[0].strip().lower()), re.I)
#   tcp_app_matching = re.search(r"tcp", str(application_split[0].strip().lower()), re.I)
#   udp_app_matching = re.search(r"udp", str(application_split[0].strip().lower()), re.I)
#   icmp_app_matching = re.search(r"icmp", str(application_split[0].strip().lower()), re.I)
#   #
#   if any_app_matching or interger_any_app_matching or tcp_app_matching or udp_app_matching:
#   #if re.search(r"tcp", application_split[0].strip().lower(), re.I) or re.search(r"udp", application_split[0].strip().lower(), re.I):
#     [ _proto_, _port_range_ ] = application_split
#     portrange_split = _port_range_.strip().split("-")
#     [ _start_port_, _end_port_ ] = portrange_split
#   else:
#     #if re.search(r"icmp", application_split[0].strip().lower(), re.I):
#     if icmp_app_matching:
#       return file_database[unicode(r"icmp")]
#   # tcp udp processing
#   return_matched_list = []
#   _keyname_database_ = file_database.keys()
#   for _keyname_ in _keyname_database_:    
#      #
#      _stringkeyname_values_ = str(_keyname_)
#      #
#      _any_app_match_ = re.search(r"any", _stringkeyname_values_.lower(), re.I)
#      _interger_any_app_match_ = re.search(r"0", _stringkeyname_values_.lower(), re.I)
#      _tcp_app_match_ = re.search(r"tcp", _stringkeyname_values_.lower(), re.I)
#      _udp_app_match_ = re.search(r"udp", _stringkeyname_values_.lower(), re.I)
#      _icmp_app_match_ = re.search(r"icmp", _stringkeyname_values_.lower(), re.I)             
#      # 
#      #if re.search(r"tcp", str(_keyname_), re.I) or re.search(r"udp", str(_keyname_), re.I):
#      if _any_app_match_ or _interger_any_app_match_ or _tcp_app_match_ or _udp_app_match_:
#        key_split = _keyname_.strip().split("/")
#        [ _key_proto_, _key_port_range_ ] = key_split    
#        keyport_split = _key_port_range_.strip().split("-")
#        [ _key_start_port_, _key_end_port_ ] = keyport_split
#        if re.match(str(_proto_).lower(),str(_key_proto_).lower(),re.I):
#          keyportragne_list = range(int(_key_start_port_),int(_key_end_port_)+int(1))
#          portragne_list = range(int(_start_port_),int(_end_port_)+int(1))
#          if len(portragne_list) <= len(keyportragne_list):
#            if set(portragne_list).intersection(keyportragne_list) == set(portragne_list):
#              return_matched_list = return_matched_list + file_database[_keyname_]
#          else:
#            if set(portragne_list).intersection(keyportragne_list) == set(keyportragne_list):
#              return_matched_list = return_matched_list + file_database[_keyname_]
#      else:
#        #if re.search(r"icmp", str(_keyname_), re.I):
#        if _icmp_app_match_:
#          continue
#   return return_matched_list

#def perfect_match_lookup_function(srcnetip_file_database, dstnetip_file_database, srcapp_file_database, dstapp_file_database, inputsrc_netip, inputdst_netip, src_proto_port_string, dst_proto_port_string):
#   perfect_matched_policylist = []
#   source_in_filedb_list = []
#   destination_in_filedb_list = []
#   application_in_filedb_list = []
#   source_in_filedb_list  = get_listvalue_matchedby_keyname(srcnetip_file_database, inputsrc_netip)
#   destination_in_filedb_list  = get_listvalue_matchedby_keyname(dstnetip_file_database, inputdst_netip)
#   src_application_in_filedb_list = get_listvalue_matchedby_keyname(srcapp_file_database, src_proto_port_string)
#   dst_application_in_filedb_list = get_listvalue_matchedby_keyname(dstapp_file_database, dst_proto_port_string)
#   matched_policylist = []
#   if len(source_in_filedb_list)*len(destination_in_filedb_list)*len(src_application_in_filedb_list)*len(dst_application_in_filedb_list):
#     matched_policylist = compare_srcdstapplist(source_in_filedb_list,destination_in_filedb_list,src_application_in_filedb_list,dst_application_in_filedb_list)
#   return matched_policylist    

#def include_match_lookup_function(srcnetip_file_database, dstnetip_file_database, srcapp_file_database, dstapp_file_database, inputsrc_netip, inputdst_netip, src_proto_port_string, dst_proto_port_string):
#   included_matched_policylist = []
#   source_in_filedb_list = []
#   destination_in_filedb_list = []
#   application_in_filedb_list = []
#   source_in_filedb_list = compare_including_netip(srcnetip_file_database, inputsrc_netip)
#   destination_in_filedb_list = compare_including_netip(dstnetip_file_database, inputdst_netip)
#   src_application_in_filedb_list = compare_including_application(srcapp_file_database, src_proto_port_string)
#   dst_application_in_filedb_list = compare_including_application(dstapp_file_database, dst_proto_port_string)
#   matched_policylist = []
#   if len(source_in_filedb_list)*len(destination_in_filedb_list)*len(src_application_in_filedb_list)*len(dst_application_in_filedb_list):
#     matched_policylist = compare_srcdstapplist(source_in_filedb_list,destination_in_filedb_list,src_application_in_filedb_list,dst_application_in_filedb_list)
#   return matched_policylist    

#def patial_match_lookup_function(srcnetip_file_database, dstnetip_file_database, srcapp_file_database, dstapp_file_database, inputsrc_netip, inputdst_netip, src_proto_port_string, dst_proto_port_string):
#   source_in_filedb_list = []
#   destination_in_filedb_list = []
#   application_in_filedb_list = []
#   source_in_filedb_list = partial_includ_match_netip(srcnetip_file_database, inputsrc_netip)
#   destination_in_filedb_list = partial_includ_match_netip(dstnetip_file_database, inputdst_netip)
#   src_application_in_filedb_list = partial_including_application(srcapp_file_database, src_proto_port_string)
#   dst_application_in_filedb_list = partial_including_application(dstapp_file_database, dst_proto_port_string)
#   matched_policylist = []
#   if len(source_in_filedb_list)*len(destination_in_filedb_list)*len(src_application_in_filedb_list)*len(dst_application_in_filedb_list):
#     matched_policylist = compare_srcdstapplist(source_in_filedb_list,destination_in_filedb_list,src_application_in_filedb_list,dst_application_in_filedb_list)
#   return matched_policylist    


def findout_policydetail_from_cache(_rulename_list_, device_fromtozone_string, file_database):
   policy_detail = {}
   for _rulename_string_ in _rulename_list_:
      if unicode(_rulename_string_) not in policy_detail.keys():
        unique_string_name = "%(_rulename_string_)s@%(device_fromtozone_string)s" % {"_rulename_string_":str(_rulename_string_), "device_fromtozone_string":str(device_fromtozone_string)}
        policy_detail[unicode(_rulename_string_)] = file_database[unicode(unique_string_name)] 
   return policy_detail
      

def _get_tcpudp_all_(_dictvalues_):
   tcp_string = "tcp/"
   udp_string = "udp/"
   tcp_all = []
   udp_all = []
   keyname_list = _dictvalues_.keys()
   for _keyname_ in keyname_list:
      #
      if re.search(tcp_string, _keyname_, re.I):
        for _id_ in _dictvalues_[_keyname_]:
           if _id_ not in tcp_all:
             tcp_all.append(_id_)
      #
      if re.search(udp_string, _keyname_, re.I):
        for _id_ in _dictvalues_[_keyname_]:
           if _id_ not in udp_all:
             udp_all.append(_id_)
   return tcp_all, udp_all

def _add_stringvalue_into_the_dictionary_(inputsrc_netip, _keystring_, searched_target_items):
   if _keystring_ not in searched_target_items.keys():
     searched_target_items[_keystring_] = ""
   if inputsrc_netip not in searched_target_items[_keystring_]:
     searched_target_items[_keystring_] = inputsrc_netip
   return searched_target_items

def _add_stringvalues_into_the_dictionaries_for_application_(_srcapp_keystring_, _dstapp_keystring_, searched_target_items, _srcapp_value_, _dstapp_value_):
   if _srcapp_keystring_ not in searched_target_items.keys():
     searched_target_items[_srcapp_keystring_] = ""
   if _dstapp_keystring_ not in searched_target_items.keys():
     searched_target_items[_dstapp_keystring_] = ""
   searched_target_items[_srcapp_keystring_] = str(_srcapp_value_)
   searched_target_items[_dstapp_keystring_] = str(_dstapp_value_)
   return searched_target_items

def _add_string_into_list_during_(_listvalue_, _temp_include_id_list_):
   for _id_ in _listvalue_:
      if _id_ not in _temp_include_id_list_:
        _temp_include_id_list_.append(_id_)
   return _temp_include_id_list_ 

def _getrangelist_from_range_(_range_string_):
   splited_range = _range_string_.split("-")
   [ _start_, _end_ ] = splited_range
   _all_rangelist_ = range(int(_end_))
   _all_rangelist_.append(int(_end_))
   range_valuelist = _all_rangelist_[int(_start_):]
   return range_valuelist

def _obtain_perfect_include_partial_application_(input_value, _netip_list_from_database_, database_dict, portrange_list, _temp_perfect_match_, _temp_include_match_, _temp_partial_match_):
   # perfect match
   if input_value in database_dict.keys():
     _temp_perfect_match_ = database_dict[input_value]
   for _netip_from_database_ in _netip_list_from_database_:
      [ prototype_from_database, portrange_from_database ] =  str(_netip_from_database_).strip().split("/")
      portrange_list_from_database = _getrangelist_from_range_(portrange_from_database)
      intersection_portrange = set(portrange_list).intersection(portrange_list_from_database)
      # include
      if intersection_portrange == set(portrange_list):
        _temp_include_match_ = _add_string_into_list_during_(database_dict[_netip_from_database_], _temp_include_match_)
      # partial
      if intersection_portrange == set(portrange_list_from_database):
        _temp_partial_match_ = _add_string_into_list_during_(database_dict[_netip_from_database_], _temp_partial_match_)
   return _temp_perfect_match_, _temp_include_match_, _temp_partial_match_
  
#   if input_value in _netip_list_from_database_:
#     # perfect match
#     _temp_perfect_match_ = database_dict[input_value]
#   else:
#     for _netip_from_database_ in _netip_list_from_database_:
#        [ prototype_from_database, portrange_from_database ] =  str(_netip_from_database_).strip().split("/")
#        portrange_list_from_database = _getrangelist_from_range_(portrange_from_database)
#        intersection_portrange = set(portrange_list).intersection(portrange_list_from_database)
#        # include
#        if intersection_portrange == set(portrange_list):
#          _temp_include_match_ = _add_string_into_list_during_(database_dict[_netip_from_database_], _temp_include_match_)
#        # partial
#        if intersection_portrange == set(portrange_list_from_database):
#          _temp_partial_match_ = _add_string_into_list_during_(database_dict[_netip_from_database_], _temp_partial_match_)
#   return _temp_perfect_match_, _temp_include_match_, _temp_partial_match_

def _multiple_intersection_(_list_in_lists_):
   intersection_value = _list_in_lists_[0]
   for _listvalue_ in _list_in_lists_[1:]:
      intersection_value = set(intersection_value).intersection(_listvalue_)
   return list(intersection_value)

def procesing_searchingzone(_netip_, routing_info_per_devicehost, this_processor_queue):
   #
   _this_subnet_ = int(str(_netip_).split('/')[-1])
   _this_IPNetwork = IPNetwork(str(_netip_))

   # search and find default routing and zone 
   _default_gateway_zone_ = ''
   for _dictvalues_ in routing_info_per_devicehost:
      if re.search('0.0.0.0/0', _dictvalues_[u'routing_address'], re.I):
        _default_gateway_zone_ = _dictvalues_[u'zonename']
        break
   #
   logested_matched_routing = []
   #
   matched_routing = {}
   for _dictvalues_ in routing_info_per_devicehost:
      _in_subnet_ = int(str(_dictvalues_[u'routing_address']).split('/')[-1])
      if not re.search('0.0.0.0/0', str(_dictvalues_[u'routing_address'])):
        if _this_IPNetwork in IPNetwork(str(_dictvalues_[u'routing_address'])):
          if _in_subnet_ not in matched_routing.keys():
            matched_routing[_in_subnet_] = []
          matched_routing[_in_subnet_].append(_dictvalues_)
   #
   _subnets_list_ = matched_routing.keys()
   _subnets_list_.sort()
   if len(_subnets_list_):
     _subnet_max_ = _subnets_list_[-1]
     for _dictvalues_ in matched_routing[_subnet_max_]:
        _unique_string_ = '#unique#'.join([str(_netip_), str(_dictvalues_[u'devicehostname']), str(_dictvalues_[u'apiaccessip']), str(_dictvalues_[u'zonename']), str(_dictvalues_[u'routing_address'])])
        _selected_value_ = {'searching_netip':str(_netip_), 'devicehostname':str(_dictvalues_[u'devicehostname']), 'apiaccessip':str(_dictvalues_[u'apiaccessip']), 'zonename':str(_dictvalues_[u'zonename']), 'routing_address':str(_dictvalues_[u'routing_address']), 'unique_string':_unique_string_}
        logested_matched_routing.append(_selected_value_)

   #
   matched_routing = {}
   for _dictvalues_ in routing_info_per_devicehost:
      _in_subnet_ = int(str(_dictvalues_[u'routing_address']).split('/')[-1])
      if not re.search('0.0.0.0/0', str(_dictvalues_[u'routing_address'])):
        if IPNetwork(str(_dictvalues_[u'routing_address'])) in _this_IPNetwork:
          _unique_string_ = '#unique#'.join([str(_dictvalues_[u'routing_address']), str(_dictvalues_[u'devicehostname']), str(_dictvalues_[u'apiaccessip']), str(_dictvalues_[u'zonename']), str(_dictvalues_[u'routing_address'])])
          _selected_value_ = {'searching_netip':str(_dictvalues_[u'routing_address']), 'devicehostname':str(_dictvalues_[u'devicehostname']), 'apiaccessip':str(_dictvalues_[u'apiaccessip']), 'zonename':str(_dictvalues_[u'zonename']), 'routing_address':str(_dictvalues_[u'routing_address']), 'unique_string':_unique_string_}
          _added_status_ = True
          for _dict_ in logested_matched_routing:
             if re.search(_unique_string_, _dict_['unique_string']):
               _added_status_ = False 
          if _added_status_:
            logested_matched_routing.append(_selected_value_)


#          if _in_subnet_ not in matched_routing.keys():
#            matched_routing[_in_subnet_] = []
#          matched_routing[_in_subnet_].append(_dictvalues_)

#   _subnets_list_ = matched_routing.keys()
#   _subnets_list_.sort()
#   if len(_subnets_list_):
#     _subnet_max_ = _subnets_list_[-1]
#     for _dictvalues_ in matched_routing[_subnet_max_]:
#        _unique_string_ = '#unique#'.join([str(_dictvalues_[u'routing_address']), str(_dictvalues_[u'devicehostname']), str(_dictvalues_[u'apiaccessip']), str(_dictvalues_[u'zonename']), str(_dictvalues_[u'routing_address'])])
#        _selected_value_ = {'searching_netip':str(_dictvalues_[u'routing_address']), 'devicehostname':str(_dictvalues_[u'devicehostname']), 'apiaccessip':str(_dictvalues_[u'apiaccessip']), 'zonename':str(_dictvalues_[u'zonename']), 'routing_address':str(_dictvalues_[u'routing_address']), 'unique_string':_unique_string_}
#        _added_status_ = True
#        for _dict_ in logested_matched_routing:
#           if re.search(_unique_string_, _dict_['unique_string']):
#             _added_status_ = False
#        if _added_status_:
#          logested_matched_routing.append(_selected_value_)
   #
   searched_routing_list = {}
   for _dictvalues_ in logested_matched_routing:
      _in_subnet_ = int(_dictvalues_['searching_netip'].split('/')[-1])
      if _in_subnet_ not in searched_routing_list.keys():
        searched_routing_list[_in_subnet_] = []
      searched_routing_list[_in_subnet_].append(_dictvalues_)
   _subnets_list_ = searched_routing_list.keys()
   _subnets_list_.sort()


   #count = 0


   eleminated_routing_list = []
   for _index_ in range(len(_subnets_list_)):
      if _index_ < len(_subnets_list_) - 1: 
        _subnet_max_ = _subnets_list_[_index_]
        _subnet_min_list_ = _subnets_list_[_index_+1:]
        for _dictvalues_ in searched_routing_list[_subnet_max_]:
           _coverage_status_ = True
           for _subnet_min_ in _subnet_min_list_:
              _subneted_IPNetwork_ = list(IPNetwork(_dictvalues_['searching_netip']).subnet(_subnet_min_))
              if len(_subneted_IPNetwork_) <= len(searched_routing_list[_subnet_min_]):
                for _compdict_ in searched_routing_list[_subnet_min_]:
                   if IPNetwork(_compdict_['searching_netip']) in _subneted_IPNetwork_:
                     _subneted_IPNetwork_.remove(IPNetwork(_compdict_['searching_netip']))
                if not len(_subneted_IPNetwork_):
                  _coverage_status_ = False
           if _coverage_status_:
             eleminated_routing_list.append(_dictvalues_)
      elif _index_ == len(_subnets_list_) - 1: 
        _subnet_max_ = _subnets_list_[_index_]
        for _dictvalues_ in searched_routing_list[_subnet_max_]:
           eleminated_routing_list.append(_dictvalues_)

   if len(eleminated_routing_list):
     for _dictvalues_ in eleminated_routing_list:
        if 'unique_string' in _dictvalues_.keys():
          del _dictvalues_['unique_string']
        this_processor_queue.put(_dictvalues_)
   else:
     if _default_gateway_zone_:
       this_processor_queue.put({'searching_netip':str(_netip_), 'devicehostname':str(_dictvalues_[u'devicehostname']), 'apiaccessip':str(_dictvalues_[u'apiaccessip']), 'zonename':str(_default_gateway_zone_)}) 


def procesing_searchingmatching(_each_processorData_, this_processor_queue):

   any_input_pattern = "0.0.0.0/0:0.0.0.0/0"
   any_application_pattern = "0-65535"
   app_string_pattern = "%(app_proto)s/%(service_range)s"

   for parameter_combination in _each_processorData_:
      [ inputsrc_netip, inputsrc_device, inputsrc_zone, inputdst_netip, inputdst_device, inputdst_zone, _app_value_, cache_filename ] = parameter_combination 
      string_Dictvalues = {
                            "inputsrc_netip":inputsrc_netip,
                            "inputsrc_device":inputsrc_device,
                            "inputsrc_zone":inputsrc_zone,
                            "inputdst_netip":inputdst_netip,
                            "inputdst_device":inputdst_device,
                            "inputdst_zone":inputdst_zone
                          }

      if re.match(inputsrc_device, inputdst_device, re.I):
        #
        device_fromtozone_string = "%(inputsrc_device)s_from_%(inputsrc_zone)s_to_%(inputdst_zone)s" % string_Dictvalues
        policy_cache_filename = "cachepolicy_%(device_fromtozone_string)s.txt" % {"device_fromtozone_string":device_fromtozone_string}
        #
        if (str(policy_cache_filename) in cache_filename) or (unicode(policy_cache_filename) in cache_filename):
          #
          database_filefull = USER_VAR_CHCHES + policy_cache_filename
          f = open(database_filefull,"r")
          string_contents = f.readlines()
          f.close()
          stream = BytesIO(string_contents[0])
          file_database = JSONParser().parse(stream)
          # 
          # initial valus
          tempdict_box = {}
          tempdict_box[u'sourceip'] = str(inputsrc_netip).strip().split(":")[0]
          tempdict_box[u'destinationip'] = str(inputdst_netip).strip().split(":")[0]
          tempdict_box[u'devicename'] = str(inputsrc_device)
          tempdict_box[u'fromzone'] = str(inputsrc_zone)
          tempdict_box[u'tozone'] = str(inputdst_zone)
          tempdict_box[u'applicationprototype'] = str("unknown")
          tempdict_box[u'sourceapplicationportrange'] = str("unknown")
          tempdict_box[u'destinationapplicationportrange'] = str("unknown")
          tempdict_box[u'matchedpolicy'] = {}
          tempdict_box[u'matchedpolicy'][u'perfectmatch'] = []
          tempdict_box[u'matchedpolicy'][u'includematch'] = []
          tempdict_box[u'matchedpolicy'][u'partialmatch'] = []
          tempdict_box[u'matchedpolicydetail'] = {}
          tempdict_box[u'matchedpolicydetail'][u'perfectmatch'] = {}
          tempdict_box[u'matchedpolicydetail'][u'includematch'] = {}
          tempdict_box[u'matchedpolicydetail'][u'partialmatch'] = {}

          #
          # 2017.01.16 tcp, udp, all information 
          source_tcp_any_cache, source_udp_any_cache = _get_tcpudp_all_(file_database[u"source_application"])
          destination_tcp_any_cache, destination_udp_any_cache = _get_tcpudp_all_(file_database[u"destination_application"])
          service_tcpudp_all_dictionary = {}
          service_tcpudp_all_dictionary["source_application_tcp"] = source_tcp_any_cache
          service_tcpudp_all_dictionary["source_application_udp"] = source_udp_any_cache
          service_tcpudp_all_dictionary["destination_application_tcp"] = destination_tcp_any_cache
          service_tcpudp_all_dictionary["destination_application_udp"] = destination_udp_any_cache
          
          #
          # 2017.01.16 search valid items 
          searched_target_items = {}
          if not re.search(any_input_pattern, inputsrc_netip, re.I):
            searched_target_items = _add_stringvalue_into_the_dictionary_(inputsrc_netip, "source", searched_target_items)
          if not re.search(any_input_pattern, inputdst_netip, re.I):
            searched_target_items = _add_stringvalue_into_the_dictionary_(inputdst_netip, "destination", searched_target_items)
          #
          if re.search(str("icmp"), _app_value_.strip(), re.I):
            # icmp case
            searched_target_items = _add_stringvalues_into_the_dictionaries_for_application_("source_application", "destination_application", searched_target_items, "icmp", "icmp") 
            tempdict_box[u'applicationprototype'] = str("icmp")
          else:
            # other case : tcp, udp, any, 0
            [ prototype, portrange ]  = _app_value_.strip().split("/")
            [ src_portrange, dst_portrange ] = portrange.split(":")
            srcapp_string = app_string_pattern % {"app_proto":str(prototype), "service_range":str(src_portrange)}
            dstapp_string = app_string_pattern % {"app_proto":str(prototype), "service_range":str(dst_portrange)}
            tempdict_box[u'applicationprototype'] = str(prototype)
            tempdict_box[u'sourceapplicationportrange'] = str(src_portrange)
            tempdict_box[u'destinationapplicationportrange'] = str(dstapp_string)
            if re.search(str("0"), prototype, re.I) or re.search(str("any"), prototype, re.I):
              if not re.search(any_application_pattern, srcapp_string, re.I):
                searched_target_items = _add_stringvalue_into_the_dictionary_(srcapp_string, "source_application", searched_target_items)
              if not re.search(any_application_pattern, dstapp_string, re.I):
                searched_target_items = _add_stringvalue_into_the_dictionary_(dstapp_string, "destination_application", searched_target_items)
            if re.search(str("tcp"), prototype, re.I) or re.search(str("udp"), prototype, re.I):
              searched_target_items = _add_stringvalue_into_the_dictionary_(srcapp_string, "source_application", searched_target_items)
              searched_target_items = _add_stringvalue_into_the_dictionary_(dstapp_string, "destination_application", searched_target_items)
          #
          # 2017.01.16, match value find out
          intercompare_perfect_match = []
          intercompare_include_match = []
          intercompare_partial_match = []
          compare_keyname_to_search = searched_target_items.keys()
          for _policycache_file_keyname_ in compare_keyname_to_search:
             #
             _temp_perfect_match_ = []
             _temp_include_match_ = []
             _temp_partial_match_ = []
             # network and ipaddress values
             if (_policycache_file_keyname_ == str("source")) or (_policycache_file_keyname_ == str("destination")):
               _netip_list_from_database_ = file_database[unicode(_policycache_file_keyname_)].keys()
               input_value = unicode(searched_target_items[_policycache_file_keyname_].split(":")[0])
               # perfect match
               if input_value in file_database[unicode(_policycache_file_keyname_)].keys():
                 _temp_perfect_match_ = file_database[unicode(_policycache_file_keyname_)][input_value]
               for _netip_from_database_ in _netip_list_from_database_:
                  # include match
                  if (IPNetwork(input_value) in IPNetwork(_netip_from_database_)) and (IPNetwork(input_value) != IPNetwork(_netip_from_database_)):
                    _temp_include_match_ = _add_string_into_list_during_(file_database[unicode(_policycache_file_keyname_)][_netip_from_database_], _temp_include_match_)
                  # partial match
                  if (IPNetwork(_netip_from_database_) in IPNetwork(input_value)) and (IPNetwork(input_value) != IPNetwork(_netip_from_database_)):
                    _temp_partial_match_ = _add_string_into_list_during_(file_database[unicode(_policycache_file_keyname_)][_netip_from_database_], _temp_partial_match_)


               #if input_value in _netip_list_from_database_:
               #  # perfect match
               #  _temp_perfect_match_ = file_database[unicode(_policycache_file_keyname_)][input_value]

               #else:

               #  for _netip_from_database_ in _netip_list_from_database_:
               #     # include match
               #     if IPNetwork(input_value) in IPNetwork(_netip_from_database_):
               #       _temp_include_match_ = _add_string_into_list_during_(file_database[unicode(_policycache_file_keyname_)][_netip_from_database_], _temp_include_match_)
               #     # partial match
               #     if IPNetwork(_netip_from_database_) in IPNetwork(input_value):
               #       _temp_partial_match_ = _add_string_into_list_during_(file_database[unicode(_policycache_file_keyname_)][_netip_from_database_], _temp_partial_match_)

             # application
             elif (_policycache_file_keyname_ == str("source_application")) or (_policycache_file_keyname_ == str("destination_application")):
               _netip_list_from_database_ = file_database[unicode(_policycache_file_keyname_)].keys()
               input_value = unicode(searched_target_items[_policycache_file_keyname_])
               if re.search(str("icmp"), str(input_value), re.I):
                 if unicode("icmp") in file_database[unicode(_policycache_file_keyname_)].keys():
                   _temp_perfect_match_ = file_database[unicode(_policycache_file_keyname_)][u"icmp"]
               else:
                 # any, tcp udp case
                 [ prototype, portrange ]  = searched_target_items[_policycache_file_keyname_].strip().split("/")
                 portrange_list = _getrangelist_from_range_(portrange)    
                 #
                 remove_icmp_netip_list_from_database_ = copy.copy(_netip_list_from_database_)
                 if u"icmp" in remove_icmp_netip_list_from_database_:
                   remove_icmp_netip_list_from_database_.remove(u"icmp")
                 #
                 if re.search(str("0"), prototype, re.I) or re.search(str("any"), prototype, re.I):


                   _temp_perfect_match_, _temp_include_match_, _temp_partial_match_ = _obtain_perfect_include_partial_application_(input_value, remove_icmp_netip_list_from_database_, file_database[unicode(_policycache_file_keyname_)], portrange_list, _temp_perfect_match_, _temp_include_match_, _temp_partial_match_)
                 elif re.search(str("tcp"), prototype, re.I) or re.search(str("udp"), prototype, re.I):
                   if re.search(any_application_pattern, portrange, re.I):
                     _allservice_keyname_ = "%(_policycache_file_keyname_)s_%(prototype)s" % {"_policycache_file_keyname_":_policycache_file_keyname_, "prototype":prototype}
                     _allservice_id_list_ = service_tcpudp_all_dictionary[_allservice_keyname_]
                     _temp_perfect_match_ = _allservice_id_list_
                     _temp_include_match_ = _allservice_id_list_
                     _temp_partial_match_ = _allservice_id_list_
                   else:
                     _temp_perfect_match_, _temp_include_match_, _temp_partial_match_ = _obtain_perfect_include_partial_application_(input_value, remove_icmp_netip_list_from_database_, file_database[unicode(_policycache_file_keyname_)], portrange_list, _temp_perfect_match_, _temp_include_match_, _temp_partial_match_)
             #
             intercompare_perfect_match.append(_temp_perfect_match_)
             intercompare_include_match.append(_temp_include_match_)
             intercompare_partial_match.append(_temp_partial_match_)
          # 2017.01.16, match value find out
          tempdict_box[u'matchedpolicy'][u'perfectmatch'] = _multiple_intersection_(intercompare_perfect_match)
          tempdict_box[u'matchedpolicy'][u'includematch'] = _multiple_intersection_(intercompare_include_match)
          tempdict_box[u'matchedpolicy'][u'partialmatch'] = _multiple_intersection_(intercompare_partial_match)
          tempdict_box[u'matchedpolicydetail'][u'perfectmatch'] = findout_policydetail_from_cache(tempdict_box[u'matchedpolicy'][u'perfectmatch'], device_fromtozone_string, file_database[u'policydetail'])
          tempdict_box[u'matchedpolicydetail'][u'includematch'] = findout_policydetail_from_cache(tempdict_box[u'matchedpolicy'][u'includematch'], device_fromtozone_string, file_database[u'policydetail'])
          tempdict_box[u'matchedpolicydetail'][u'partialmatch'] = findout_policydetail_from_cache(tempdict_box[u'matchedpolicy'][u'partialmatch'], device_fromtozone_string, file_database[u'policydetail'])

           

          # insert the queue
          this_processor_queue.put(tempdict_box)
 
   print "processor is completed....!"
   time.sleep(1)



def _findout_matched_zone_(routing_info_per_devicehost, _netip_, _candi_src_netip_):
   processing_queues_list = []
   for _devicehost_ in routing_info_per_devicehost.keys():
      processing_queues_list.append(Queue(maxsize=0))
   # run processing to get zone based information
   count = 0
   _processor_list_ = []
   for _devicehost_ in routing_info_per_devicehost.keys():
      this_processor_queue = processing_queues_list[count]
      _processor_ = Process(target = procesing_searchingzone, args = (_netip_, routing_info_per_devicehost[_devicehost_], this_processor_queue,))
      _processor_.start()
      _processor_list_.append(_processor_)
      count = count + 1
   #
   for _processor_ in _processor_list_:
      _processor_.join()
   #
   for _queue_ in processing_queues_list:
      while not _queue_.empty():
           _get_values_ = _queue_.get()
           _candi_src_netip_.append(_get_values_)
   return _candi_src_netip_



@api_view(['GET','POST'])
@csrf_exempt
def juniper_searchpolicy(request,format=None):

   #global tatalsearched_values, threadlock_key
   #threadlock_key = threading.Lock()
   #tatalsearched_values = []



   # get method
   if request.method == 'GET':
     parameter_from = request.query_params.dict()
     _keyname_pattern_ = "([a-zA-Z0-9\-\.\/\_\<\>\-\:\*]*)_from_([a-zA-Z0-9\-\.\/\_\<\>\-\:\*]*)_to_([a-zA-Z0-9\-\.\/\_\<\>\-\:\*]*)"
     if u'devicehostname' not in parameter_from:
       hostname_list = []
       for _dictvalues_ in obtainjson_from_mongodb('juniper_srx_rule_table_cache'):       
          _keyname_ = "%(_host_)s_from_%(_from_)s_to_%(_to_)s" % {'_host_':_dictvalues_[u'devicehostname'], '_from_':_dictvalues_[u'from_zone'], '_to_':_dictvalues_[u'to_zone']}
          if _keyname_ not in hostname_list:
            hostname_list.append(_keyname_) 
       return Response(json.dumps({"items":hostname_list}))
     else:
       parameter_hostname = parameter_from[u'devicehostname'] 
       searched_value = re.search(_keyname_pattern_, str(parameter_hostname))
       if searched_value:
         _target_ = {"devicehostname":searched_value.group(1).strip(),"from_zone":searched_value.group(2).strip(),"to_zone":searched_value.group(3).strip()}
         _obtained_values_ = exact_findout('juniper_srx_rule_table_cache', _target_)
         for _dictvalues_ in _obtained_values_:
            del _dictvalues_[u'_id']
         return Response(json.dumps({"items":_obtained_values_}))



   elif request.method == 'POST':
       if re.search(r"system", system_property["role"], re.I):
         _input_ = JSONParser().parse(request)

         #
         device_information_values = obtainjson_from_mongodb('juniper_srx_devices')
         primary_devices = findout_primary_devices(device_information_values)

         # confirm input type 
         if type(_input_) != type({}):
           return_object = {"items":[{"message":"input should be object or dictionary!!","process_status":"error"}]}
           return Response(json.dumps(return_object))
         #
         _searching_target_ = []
         if not re.search('0.0.0.0/0', _input_[u'src_netip']):
           _searching_target_.append(u'src_netip') 
         if not re.search('0.0.0.0/0', _input_[u'dst_netip']):
           _searching_target_.append(u'dst_netip')
         if not re.search('0\/[0-9]+\-65535', _input_[u'src_port']) and not re.search('0\/[0-9]+\-0', _input_[u'src_port']):
           _searching_target_.append(u'src_port')
         if not re.search('0\/[0-9]+\-65535', _input_[u'dst_port']) and not re.search('0\/[0-9]+\-0', _input_[u'dst_port']):
           _searching_target_.append(u'dst_port')

         #
         _routing_table_ = obtainjson_from_mongodb('juniper_srx_routingtable')
         if not len(_routing_table_):
           return_object = {"items":[{"message":"there is no routing table registered!!","process_status":"error"}]}
           return Response(json.dumps(return_object))
         #
         routing_info_per_devicehost = {}
         for _dictvalues_ in _routing_table_:
            if _dictvalues_[u"apiaccessip"] in primary_devices:
              _devicehost_ = _dictvalues_[u'devicehostname']
              if _devicehost_ not in routing_info_per_devicehost.keys():
                routing_info_per_devicehost[_devicehost_] = []
              routing_info_per_devicehost[_devicehost_].append(_dictvalues_)

         # findout source zone
         _candi_src_netip_ = []
         if u'src_netip' in _searching_target_:
           _netip_ = _input_[u'src_netip']
           _candi_src_netip_ = _findout_matched_zone_(routing_info_per_devicehost, _netip_, _candi_src_netip_)

         # findout destination zone
         _candi_dst_netip_ = []
         if u'dst_netip' in _searching_target_:
           _netip_ = _input_[u'dst_netip']
           _candi_dst_netip_ = _findout_matched_zone_(routing_info_per_devicehost, _netip_, _candi_dst_netip_)

         # intersection
         _candi_comb_ = []
         for _src_dictvalue_ in _candi_src_netip_:
            for _dst_dictvalue_ in _candi_dst_netip_:
               if re.match(str(_src_dictvalue_['devicehostname']), str(_dst_dictvalue_['devicehostname'])):
                 if not re.match(str(_src_dictvalue_['zonename']), str(_dst_dictvalue_['zonename'])):
                   _candi_comb_.append({'src_netip':_src_dictvalue_ ,'dst_netip':_dst_dictvalue_})
         # 
         if u'src_port' in _searching_target_:
           for _dictvalue_ in _candi_comb_:
              _dictvalue_[u'src_port'] = _input_[u'src_port']
         #
         if u'dst_port' in _searching_target_:
           for _dictvalue_ in _candi_comb_:
              _dictvalue_[u'dst_port'] = _input_[u'dst_port']
                     
         print _candi_comb_ 


         #print routing_info_per_devicehost 
         #print _input_
         #
         return Response(json.dumps({}))
          


       # end of if re.search(r"system", system_property["role"], re.I):
       else:
         return_object = {"items":[{"message":"this host has no authorizaition!","process_status":"error"}]}
         return Response(json.dumps(return_object))

#      try:
#
#        # input
#        _input_ = JSONParser().parse(request)
#
#        # cache directory
#        cache_filename = []
#        for _fname_ in os.listdir(USER_VAR_CHCHES):
#           if re.search("cachepolicy_", _fname_.strip(), re.I):
#             if _fname_ not in cache_filename:
#               cache_filename.append(_fname_)
#
#        # get devicelist
#        CURL_command = "curl http://0.0.0.0:"+RUNSERVER_PORT+"/juniper/devicelist/"
#        get_info = os.popen(CURL_command).read().strip()
#        stream = BytesIO(get_info)
#        _routing_dict_ = JSONParser().parse(stream)
#
#        CURL_command = "curl -H \"Accept: application/json\" -X POST -d \'"+json.dumps(_input_)+"\' http://0.0.0.0:"+RUNSERVER_PORT+"/juniper/searchzonefromroute/"
#        get_info = os.popen(CURL_command).read().strip()
#        stream = BytesIO(get_info)
#        data_from_CURL_command = JSONParser().parse(stream)
#
#        #
#        every_parameter_combination_list = []
#        for _dictData_ in data_from_CURL_command:
#           for _src_string_ in _dictData_[u"sourceip"]:
#              [ inputsrc_netip, inputsrc_device, inputsrc_zone ] = parsing_filename_to_data(_routing_dict_,_src_string_)
#              for _dst_value_ in _dictData_[u"destinationip"]:
#                 [ inputdst_netip, inputdst_device, inputdst_zone ] = parsing_filename_to_data(_routing_dict_,_dst_value_)
#                 if re.match(inputsrc_device, inputdst_device, re.I):
#                   for _app_value_ in _dictData_[u"application"]:
#                      parameter_combination = [ inputsrc_netip, inputsrc_device, inputsrc_zone, inputdst_netip, inputdst_device, inputdst_zone, _app_value_, cache_filename ]
#                      every_parameter_combination_list.append(parameter_combination)
#
#        # init 
#        processing_combination = []
#        processing_queue = []
#        if len(every_parameter_combination_list) <= int(PYTHON_MULTI_PROCESS): 
#          for _i_ in range(len(every_parameter_combination_list)):
#             processing_combination.append([])
#             processing_queue.append(Queue(maxsize=0))
#        else:
#          for _i_ in range(int(PYTHON_MULTI_PROCESS)):
#             processing_combination.append([])
#             processing_queue.append(Queue(maxsize=0))
#        #
#        print "Total number of Data : %(_tnumber_)s.... planned with queues for the processing...." % {"_tnumber_":str(len(processing_combination))}
#        count = 0
#        for parameter_combination in every_parameter_combination_list:
#           (_values_, _last_) = divmod(count, int(int(PYTHON_MULTI_PROCESS)))
#           processing_combination[_last_].append(parameter_combination)
#           count = count + 1   
#        print "datas are divied..!"
#        #
#        count = 0
#        _processor_list_ = []
#        for _each_processorData_ in processing_combination:
#           this_processor_queue = processing_queue[count]
#           _processor_ = Process(target = procesing_searchingmatching, args = (_each_processorData_, this_processor_queue,)) 
#           _processor_.start()
#           _processor_list_.append(_processor_) 
#           count = count + 1 
#        for _processor_ in _processor_list_:
#           _processor_.join()
#        #
#        search_result = [] 
#        for _queue_ in processing_queue:
#           while not _queue_.empty():
#                search_result.append(_queue_.get())
#        #
#        return Response(search_result)
#
#      except:
#        message = "Post Algorithm has some problem!"
#        return Response(message, status=status.HTTP_400_BAD_REQUEST)
#
