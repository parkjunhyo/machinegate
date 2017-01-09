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

import os,re,copy,json,time,threading,sys
import paramiko
from netaddr import *

class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders its content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)

def proper_routingtable(routingtable_matched):
   routingtable_netvalues = {}
   for _routing_element_ in routingtable_matched:
      _keyname_in_element_ = _routing_element_.keys()
      for _expected_values_ in _keyname_in_element_:
         if re.search("/[0-9]+",str(_expected_values_),re.I):
           if _expected_values_ not in routingtable_netvalues.keys():
             routingtable_netvalues[_expected_values_] = _routing_element_[_expected_values_]
   return routingtable_netvalues
   
def logest_matching(possible_sourceip_list):
   # device name findout
   valid_devicelist = []
   for _ippattern_ in possible_sourceip_list:
      _devicename_ = str(str(str(_ippattern_).strip().split("@")[1]).strip().split(":")[0])
      if _devicename_ not in valid_devicelist:
        valid_devicelist.append(_devicename_)
   # 
   return_list = []
   for _devicename_ in valid_devicelist:
      _network_values_list_ = []
      for _ippattern_ in possible_sourceip_list:
         if re.search(str(_devicename_),str(_ippattern_),re.I):
           network_routingtable = str(str(_ippattern_).strip().split("@")[0])
           network_value = network_routingtable.strip().split(":")[0]
           if str(network_value) not in _network_values_list_:
             _network_values_list_.append(str(network_value))
      for _valid_network_ in _network_values_list_:
         dictbox_temp = {}
         for _ippattern_ in possible_sourceip_list:
            if re.search(str(_devicename_),str(_ippattern_),re.I) and re.search("%(_network_)s:" % {"_network_":str(_valid_network_)},str(_ippattern_),re.I):
              network_routingtable = str(str(_ippattern_).strip().split("@")[0])
              network_value = network_routingtable.strip().split(":")[1]
              network_subnet = int(network_value.strip().split("/")[-1])
              if network_subnet not in dictbox_temp.keys():
                dictbox_temp[network_subnet] = []
              dictbox_temp[network_subnet].append(_ippattern_)
         # max find
         _keyname_ = dictbox_temp.keys()
         _keyname_.sort()
         max_value = _keyname_[-1]
         return_list = return_list + dictbox_temp[max_value]
   return return_list


def source_destination_routinglookup(source_ip_list,primarysecondary_devicelist,primarysecondary_devicename,primarysecondary_interfaces,primarysecondary_zonesname,routingtable_inmemory):
   possible_sourceip_list = []
   for _sourceip_ in source_ip_list:
      #
      _source_net_ = IPNetwork(unicode(_sourceip_))
      _source_subnet_ = str(str(_source_net_).strip().split("/")[-1])
      #
      for _deviceip_ in primarysecondary_devicelist:
         #
         interface_property = []
         for _interfacename_ in primarysecondary_interfaces[_deviceip_].keys():
            _property_ = primarysecondary_interfaces[_deviceip_][_interfacename_][u"interfacemode"]
            if _property_ not in interface_property:
              interface_property.append(_property_)
         #
         _devicename_ = primarysecondary_devicename[_deviceip_]
         if (str("bridgemode") in interface_property) or (unicode("bridgemode") in interface_property):
           for _zonename_ in primarysecondary_zonesname[_deviceip_]:
              _instring_ = "%(_network_)s:0.0.0.0/0@%(_devicename_)s:%(_deviceip_)s:%(_zone_)s" % {"_network_":str(_source_net_),"_deviceip_":str(_deviceip_),"_devicename_":str(_devicename_),"_zone_":str(_zonename_)}
              if str(_instring_) not in possible_sourceip_list:
                possible_sourceip_list.append(str(_instring_))
         else:
           #
           routingtable_matched = routingtable_inmemory[_deviceip_]
           routingtable_netvalues = proper_routingtable(routingtable_matched)
           routingtable_network_values = routingtable_netvalues.keys()
           for _network_value_ in routingtable_network_values:
              #
              _route_net_ = IPNetwork(unicode(_network_value_))
              _route_subnet_ = str(str(_route_net_).strip().split("/")[-1])
              #
              _zonename_ = routingtable_netvalues[_network_value_][u'zonename']
              if int(_route_subnet_) <= int(_source_subnet_):
                if _source_net_ in _route_net_:
                  _instring_ = "%(_network_)s:%(_route_)s@%(_devicename_)s:%(_deviceip_)s:%(_zone_)s" % {"_network_":str(_source_net_),"_deviceip_":str(_deviceip_),"_devicename_":str(_devicename_),"_zone_":str(_zonename_),"_route_":str(_route_net_)}
                  if str(_instring_) not in possible_sourceip_list:
                    possible_sourceip_list.append(str(_instring_))
              else:
                if _route_net_ in _source_net_:
                  _instring_ = "%(_network_)s:%(_route_)s@%(_devicename_)s:%(_deviceip_)s:%(_zone_)s" % {"_network_":str(_route_net_),"_deviceip_":str(_deviceip_),"_devicename_":str(_devicename_),"_zone_":str(_zonename_),"_route_":str(_source_net_)}
                  if str(_instring_) not in possible_sourceip_list:
                    possible_sourceip_list.append(str(_instring_))
   return possible_sourceip_list 

def devicename_from_ipaddress(_datalist_):
   src_list = []
   for _sourceip_ in _datalist_:
      source_device = str(str(str(_sourceip_).strip().split("@")[-1]).strip().split(":")[0])
      if source_device not in src_list:
        src_list.append(source_device)
   return src_list

def matchvalue_by_devicename(_datalist_,_devicename_):
   matched_src_values = []
   for _info_ in _datalist_:
      if re.search(str(_devicename_),str(_info_),re.I):
        if str(_info_) not in matched_src_values:
          matched_src_values.append(str(_info_))
   return matched_src_values
      

def category_bydevice(full_searched_devicelist):
   #set(a).intersection(b)
   combine_list = []
   for _dictData_ in full_searched_devicelist:
      src_list = devicename_from_ipaddress(_dictData_[u"sourceip"])
      dst_list = devicename_from_ipaddress(_dictData_[u"destinationip"])

      setvalue_src_dst = set(src_list).intersection(dst_list)
      setvalue_dst_src = set(src_list).intersection(dst_list)
      if setvalue_src_dst == setvalue_dst_src:
        for _devicename_ in list(setvalue_src_dst):
           tempdict_box = {}
           tempdict_box[u"sourceip"] = matchvalue_by_devicename(_dictData_[u"sourceip"],_devicename_)
           tempdict_box[u"destinationip"] = matchvalue_by_devicename(_dictData_[u"destinationip"],_devicename_)
           tempdict_box[u"application"] = _dictData_[u"application"]
           combine_list.append(tempdict_box)
      else:
        return Response(["error, list intersection has issued!"], status=status.HTTP_400_BAD_REQUEST)    
   return combine_list

def findoutzonename(_listvalues_):
   zonelist = []
   for _string_ in _listvalues_:
      _zonename_ = str(str(_string_).strip().split(":")[-1])
      if _zonename_ not in zonelist:
        zonelist.append(_zonename_)
   return zonelist

def match_lastparse_string(_listdata_,_split_mark_,_location_,_pattern_string_):
   dictlist_box = []
   for _string_ in _listdata_:
      parsed_value = str(str(_string_).strip().split(str(_split_mark_))[int(_location_)])
      if re.search(_pattern_string_,parsed_value,re.I):
        if str(_string_) not in dictlist_box:
          dictlist_box.append(str(_string_))
   return dictlist_box

def remove_same_zonetozone_values(_rewriting_by_device_):
   uniqued_list = []
   for _dictData_values_ in _rewriting_by_device_:
      # findout zone
      _zonename_insrc_ = findoutzonename(_dictData_values_[u"sourceip"])
      _zonename_indst_ = findoutzonename(_dictData_values_[u"destinationip"])
      # 
      for _srczone_ in _zonename_insrc_:
         for _dstzone_ in _zonename_indst_:
            if not re.match(str(_srczone_),str(_dstzone_),re.I):
              tempdict_box = {}
              tempdict_box[u"sourceip"] = []
              tempdict_box[u"destinationip"] = []
              #
              tempdict_box[u"sourceip"] = match_lastparse_string(_dictData_values_[u"sourceip"],":","-1",_srczone_) 
              tempdict_box[u"destinationip"] = match_lastparse_string(_dictData_values_[u"destinationip"],":","-1",_dstzone_)
              tempdict_box[u"application"] = _dictData_values_[u"application"]
              #
              uniqued_list.append(tempdict_box)
   return uniqued_list


@api_view(['GET','POST'])
@csrf_exempt
def juniper_searchzonefromroute(request,format=None):

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
        _input_ = JSONParser().parse(request)
        # 
        for _dictData_ in _input_:
           _keyname_ = _dictData_.keys()
           if (u'destinationip' not in _keyname_) or (u'sourceip' not in _keyname_) or (u'application' not in _keyname_):
             return Response(["error, input data has missing information!"], status=status.HTTP_400_BAD_REQUEST)
 
        # validation check
        ipaddr_pattern = "[0-9]+.[0-9]+.[0-9]+.[0-9]+/[0-9]+"
        _confirmed_input_list_ = []

        # application correct matching
        _tcpudp_portmatching_ = r"[a-zA-Z0-9]+/[0-9]+-[0-9]+:[0-9]+-[0-9]+"
        _icmp_appmatching_ = r"icmp"
        for _dictData_ in _input_:
           dictBox_temp = {} 

           dictBox_temp[u'sourceip'] = []
           for _expected_ipvalue_ in str(_dictData_[u'sourceip']).strip().split(";"):
              if re.search(ipaddr_pattern,str(_expected_ipvalue_),re.I):
                if str(_expected_ipvalue_) not in dictBox_temp[u'sourceip']:
                  dictBox_temp[u'sourceip'].append(str(_expected_ipvalue_))
              else:
                return Response(["error, source ip address format has problem!"], status=status.HTTP_400_BAD_REQUEST)

           dictBox_temp[u'destinationip'] = []
           for _expected_ipvalue_ in str(_dictData_[u'destinationip']).strip().split(";"):
              if re.search(ipaddr_pattern,str(_expected_ipvalue_),re.I):
                if str(_expected_ipvalue_) not in dictBox_temp[u'destinationip']:
                  dictBox_temp[u'destinationip'].append(str(_expected_ipvalue_))
              else:
                return Response(["error, desination ip address format has problem!"], status=status.HTTP_400_BAD_REQUEST)

           dictBox_temp[u'application'] = []
           for _expected_ipvalue_ in str(_dictData_[u'application']).strip().split(";"):
              tcpudp_search_element = re.search(_tcpudp_portmatching_, str(_expected_ipvalue_).lower(), re.I)
              icmp_search_element = re.search(_icmp_appmatching_, str(_expected_ipvalue_).lower(), re.I)
              if tcpudp_search_element or icmp_search_element:
                if str(_expected_ipvalue_) not in dictBox_temp[u'application']:
                  dictBox_temp[u'application'].append(str(_expected_ipvalue_))
              else:
                return Response(["error, application format has problem!"], status=status.HTTP_400_BAD_REQUEST)
           _confirmed_input_list_.append(dictBox_temp)

        # get active devicelist
        CURL_command = "curl http://0.0.0.0:"+RUNSERVER_PORT+"/juniper/devicelist/"
        get_info = os.popen(CURL_command).read().strip()
        stream = BytesIO(get_info)
        data_from_CURL_command = JSONParser().parse(stream)
        # 
        primarysecondary_devicelist = []
        primarysecondary_devicename = {}
        primarysecondary_interfaces = {}
        primarysecondary_zonesname = {}
        for _dataDict_ in data_from_CURL_command:
           _keyname_ = _dataDict_.keys()
           if (u'apiaccessip' in _keyname_) and (u'failover' in _keyname_) and (u'failovermode' in _keyname_):
             device_add_status = False
             if _dataDict_[u'failovermode'] == "active_active":
               device_add_status = True
             else:
               pattern_string = str(_dataDict_[u'failover']).strip()
               if re.match(pattern_string,'primary',re.I):
                 device_add_status = True
             #
             if device_add_status:
               _apiaccessip_ = _dataDict_[u'apiaccessip']
               if _apiaccessip_ not in primarysecondary_devicelist:
                 primarysecondary_devicelist.append(_apiaccessip_)
                 primarysecondary_devicename[_apiaccessip_] = _dataDict_[u"devicehostname"]
                 primarysecondary_interfaces[_apiaccessip_] = _dataDict_[u"interfaces"]
                 primarysecondary_zonesname[_apiaccessip_] = _dataDict_[u"zonesname"]
        #
        #primarysecondary_devicelist = []
        #primarysecondary_devicename = {}
        #for _dataDict_ in data_from_CURL_command:
        #   _keyname_ = _dataDict_.keys()
        #   if (u'apiaccessip' in _keyname_) and (u'failover' in _keyname_):
        #     pattern_string = str(_dataDict_[u'failover']).strip()
        #     if re.match(pattern_string,'primary',re.I):
        #       _apiaccessip_ = _dataDict_[u'apiaccessip']
        #       if _apiaccessip_ not in primarysecondary_devicelist:
        #         primarysecondary_devicelist.append(_apiaccessip_)
        #         primarysecondary_devicename[_apiaccessip_] = _dataDict_[u"devicehostname"]


        # get route table information : routingtable_inmemory
        CURL_command = "curl http://0.0.0.0:"+RUNSERVER_PORT+"/juniper/showroute/"
        get_info = os.popen(CURL_command).read().strip()
        stream = BytesIO(get_info)
        data_from_CURL_command = JSONParser().parse(stream)
        routingtable_inmemory = {}
        for _dataDict_ in data_from_CURL_command:
           _keyname_ = _dataDict_.keys()
           for _key_value_ in _keyname_:
              # only get the routing information 'primary on active-statndby' and 'primary and secondary on active-active'
              if (unicode(_key_value_) in primarysecondary_devicelist) or (str(_key_value_) in primarysecondary_devicelist):
                routingtable_inmemory[_key_value_] = _dataDict_[_key_value_]

        #
        full_searched_devicelist = []
        for _dictData_ in _confirmed_input_list_:
           source_ip_list = _dictData_[u'sourceip']
           destination_ip_list = _dictData_[u'destinationip']
           # dictbox
           traybox_dict = {}
           traybox_dict[u'sourceip'] = []
           traybox_dict[u'destinationip'] = []
           traybox_dict[u'application'] = []
           # source process and after logest match
           possible_sourceip_list = source_destination_routinglookup(source_ip_list,primarysecondary_devicelist,primarysecondary_devicename,primarysecondary_interfaces,primarysecondary_zonesname,routingtable_inmemory)
           traybox_dict[u'sourceip'] = logest_matching(possible_sourceip_list)
           # destination processing
           possible_destination_list = source_destination_routinglookup(destination_ip_list,primarysecondary_devicelist,primarysecondary_devicename,primarysecondary_interfaces,primarysecondary_zonesname,routingtable_inmemory)
           traybox_dict[u'destinationip'] = logest_matching(possible_destination_list)
           # application processing
           changed_application = []
           for _expected_ipvalue_ in _dictData_[u'application']:

              _splited_prototype_portrange_ = str(_expected_ipvalue_).strip().split("/")
              expected_any_searched = re.search(r"any", str(_splited_prototype_portrange_[0].strip().lower()), re.I)
              expected_udp_searched = re.search(r"tcp", str(_splited_prototype_portrange_[0].strip().lower()), re.I)
              expected_tcp_searched = re.search(r"udp", str(_splited_prototype_portrange_[0].strip().lower()), re.I)
              expected_icmp_searched = re.search(r"icmp", str(_splited_prototype_portrange_[0].strip().lower()), re.I)

              if expected_udp_searched or expected_tcp_searched or expected_any_searched:
                [ _app_proto_, _app_portrange_ ] = _splited_prototype_portrange_
                [ _srcportrange_, _dstportrange_ ] = str(_app_portrange_).strip().split(":")
                # source port range re-define
                if re.search(str("0-0"),str(_srcportrange_),re.I) or re.search(str("0-65535"),str(_srcportrange_),re.I):
                  _srcportrange_ = str("0-65535")
                # destination port range re-define
                if re.search(str("0-0"),str(_dstportrange_),re.I) or re.search(str("0-65535"),str(_dstportrange_),re.I):
                  _dstportrange_ = str("0-65535")
                redefined_srcdstportrange_ = str(":".join([ _srcportrange_, _dstportrange_ ]))
                # protocol redefine
                if re.search("any",str(_app_proto_).lower(),re.I):
                  redefined_application = "0/%(_prange_)s;tcp/%(_prange_)s;udp/%(_prange_)s" % {"_prange_":redefined_srcdstportrange_}
                else:
                  redefined_application = "%(_proto_)s/%(_prange_)s" % {"_proto_":str(_app_proto_).lower(),"_prange_":redefined_srcdstportrange_}
                for _redef_app_ in redefined_application.split(";"):
                   if _redef_app_ not in changed_application:
                     changed_application.append(_redef_app_)
              else:
                if expected_icmp_searched:
                  if str("icmp") not in changed_application:
                    changed_application.append(str("icmp"))

              #[ _app_proto_, _app_portrange_ ] = str(_expected_ipvalue_).strip().split("/")
              #[ _srcportrange_, _dstportrange_ ] = str(_app_portrange_).strip().split(":")
              ## source port range re-define
              #if re.search(str("0-0"),str(_srcportrange_),re.I) or re.search(str("0-65535"),str(_srcportrange_),re.I):
              #  _srcportrange_ = str("0-65535")
              ## destination port range re-define
              #if re.search(str("0-0"),str(_dstportrange_),re.I) or re.search(str("0-65535"),str(_dstportrange_),re.I):
              #  _dstportrange_ = str("0-65535")      
              #redefined_srcdstportrange_ = str(":".join([ _srcportrange_, _dstportrange_ ]))                
              #if re.search("any",str(_app_proto_).lower(),re.I):
              #  redefined_application = "0/%(_prange_)s;tcp/%(_prange_)s;udp/%(_prange_)s" % {"_prange_":redefined_srcdstportrange_}
              #  for _redef_app_ in redefined_application.split(";"):
              #     if _redef_app_ not in changed_application:
              #       changed_application.append(_redef_app_)
              #else:
              #  redefined_application = "%(_proto_)s/%(_prange_)s" % {"_proto_":str(_app_proto_).lower(),"_prange_":redefined_srcdstportrange_}
              #  if redefined_application not in changed_application:
              #    changed_application.append(redefined_application)
           traybox_dict[u'application'] = changed_application
           # 
           full_searched_devicelist.append(traybox_dict)

        # re-arrange the data by the device
        _rewriting_by_device_ = category_bydevice(full_searched_devicelist)
        # re-write by the zone each device
        final_policy = remove_same_zonetozone_values(_rewriting_by_device_)
        # return
        return Response(final_policy)

      except:
        message = "Post Algorithm has some problem!"
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

