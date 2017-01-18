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
         if re.search("/[0-9]+", str(_expected_values_).strip(), re.I):
           if _expected_values_ not in routingtable_netvalues.keys():
             routingtable_netvalues[_expected_values_] = _routing_element_[_expected_values_]
   return routingtable_netvalues
   
def logest_matching(possible_sourceip_list):
   # find the device name from the input format! 
   valid_devicelist = []
   return_list = []
   anyinvalue_pattern = "0.0.0.0/0:0.0.0.0/0"
   for _ippattern_ in possible_sourceip_list:
      _devicename_ = str(str(str(_ippattern_).strip().split("@")[1]).strip().split(":")[0])
      if _devicename_ not in valid_devicelist:
        valid_devicelist.append(_devicename_)
      if re.search(anyinvalue_pattern, str(_ippattern_).strip(), re.I):
        if _ippattern_ not in return_list:
          return_list.append(_ippattern_)
   #       
   for _devicename_ in valid_devicelist:
      #
      _network_values_list_ = []
      for _ippattern_ in possible_sourceip_list:
         if re.search(str(_devicename_), str(_ippattern_), re.I):
           network_routingtable = str(str(_ippattern_).strip().split("@")[0])
           network_value = network_routingtable.strip().split(":")[0]
           if str(network_value) not in _network_values_list_:
             _network_values_list_.append(str(network_value))
      #
      for _valid_network_ in _network_values_list_:
         dictbox_temp = {}
         #
         for _ippattern_ in possible_sourceip_list:
            #
            if not re.search(anyinvalue_pattern, str(_ippattern_).strip(), re.I):
              _searching_string_ = "(%(_valid_network_)s):([0-9]+.[0-9]+.[0-9]+.[0-9]+/[0-9]+)@%(_devicename_)s" % {"_devicename_":_devicename_, "_valid_network_":_valid_network_} 
              searched_status = re.search(_searching_string_, str(_ippattern_).strip(), re.I)
              if searched_status:
                network_value = str(searched_status.group(2))
                network_subnet = int(network_value.strip().split("/")[-1])
                if network_subnet not in dictbox_temp.keys():
                  dictbox_temp[network_subnet] = []
                if _ippattern_ not in dictbox_temp[network_subnet]:
                  dictbox_temp[network_subnet].append(_ippattern_)
         # max number mean : longest matching routing values
         _keyname_ = dictbox_temp.keys()
         if len(_keyname_):
           _keyname_.sort()
           max_value = _keyname_[-1]
           return_list = return_list + dictbox_temp[max_value]
   #
   return return_list


def source_destination_routinglookup(source_ip_list,primarysecondary_devicelist,primarysecondary_devicename,primarysecondary_interfaces,primarysecondary_zonesname,routingtable_inmemory):
   possible_sourceip_list = []
   default_routing_network = IPNetwork(unicode("0.0.0.0/0"))
   _routenet_zone_string_pattern = "%(_network_)s:%(_route_)s@%(_devicename_)s:%(_deviceip_)s:%(_zone_)s"

   for _sourceip_ in source_ip_list:
      #
      _source_net_ = IPNetwork(unicode(_sourceip_))
      _source_subnet_ = str(str(_source_net_).strip().split("/")[-1])
      #
      for _deviceip_ in primarysecondary_devicelist:

         ## 2017.01.16. Any (0.0.0.0/0) case update! 
         _devicename_ = primarysecondary_devicename[_deviceip_]
         if default_routing_network == _source_net_:
           for _zonename_ in primarysecondary_zonesname[_deviceip_]:
              _instring_ = _routenet_zone_string_pattern % {"_network_":str(_source_net_),"_deviceip_":str(_deviceip_),"_devicename_":str(_devicename_),"_zone_":str(_zonename_),"_route_":str(default_routing_network)}
              if str(_instring_) not in possible_sourceip_list:
                possible_sourceip_list.append(str(_instring_))
           continue

         ## 2017.01. Birdge mode Routing Search updated!
         interface_property = []
         for _interfacename_ in primarysecondary_interfaces[_deviceip_].keys():
            _property_ = primarysecondary_interfaces[_deviceip_][_interfacename_][u"interfacemode"]
            if _property_ not in interface_property:
              interface_property.append(_property_)
         #
         #_devicename_ = primarysecondary_devicename[_deviceip_]
         #
         if (str("routedmode") in interface_property) or (unicode("routedmode") in interface_property):
           routingtable_matched = routingtable_inmemory[_deviceip_]
           routingtable_netvalues = proper_routingtable(routingtable_matched)
           routingtable_network_values = routingtable_netvalues.keys()
           for _network_value_ in routingtable_network_values:
              _route_net_ = IPNetwork(unicode(_network_value_))
              _route_subnet_ = str(str(_route_net_).strip().split("/")[-1])
              _zonename_ = routingtable_netvalues[_network_value_][u'zonename']
              if int(_route_subnet_) <= int(_source_subnet_):
                if _source_net_ in _route_net_:
                  _instring_ = _routenet_zone_string_pattern % {"_network_":str(_source_net_),"_deviceip_":str(_deviceip_),"_devicename_":str(_devicename_),"_zone_":str(_zonename_),"_route_":str(_route_net_)}
                  if str(_instring_) not in possible_sourceip_list:
                    possible_sourceip_list.append(str(_instring_))
              else:
                if _route_net_ in _source_net_:
                  _instring_ = _routenet_zone_string_pattern % {"_network_":str(_route_net_),"_deviceip_":str(_deviceip_),"_devicename_":str(_devicename_),"_zone_":str(_zonename_),"_route_":str(_source_net_)}
                  if str(_instring_) not in possible_sourceip_list:
                    possible_sourceip_list.append(str(_instring_))
         #
         else:
           # bridge mode case
           for _zonename_ in primarysecondary_zonesname[_deviceip_]:
              _instring_ = _routenet_zone_string_pattern % {"_network_":str(_source_net_),"_deviceip_":str(_deviceip_),"_devicename_":str(_devicename_),"_zone_":str(_zonename_),"_route_":str(default_routing_network)}
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

def allservice_redefine(_srcportrange_):
   if re.search(str("0-0"),str(_srcportrange_),re.I) or re.search(str("0-65535"),str(_srcportrange_),re.I) or re.search(str("1-65535"),str(_srcportrange_),re.I):
     _srcportrange_ = str("0-65535")
   return _srcportrange_


def _add_stringvalues_into_the_dictionary(_keyname_, dictBox_temp, _expected_netip_value_):
   if _keyname_ not in dictBox_temp.keys():
     dictBox_temp[_keyname_] = []
   if str(_expected_netip_value_) not in dictBox_temp[_keyname_]:
     dictBox_temp[_keyname_].append(str(_expected_netip_value_))
   return dictBox_temp

def _get_serviceproto_(_any_portmatching_, _expected_ipvalue_, _splited_prototype_portrange_):
   expected_any_searched = re.search(_any_portmatching_, str(_expected_ipvalue_).strip(), re.I)
   if expected_any_searched:
     _splited_prototype_portrange_ = expected_any_searched.group(1)
   return _splited_prototype_portrange_
   
def _redefine_servicerange_(_expected_proto_, _expected_ipvalue_):
   splite_string = "%(_expected_proto_)s/" % {"_expected_proto_":_expected_proto_}
   _app_portrange_ = _expected_ipvalue_.strip().split(splite_string)[-1]
   [ _srcportrange_, _dstportrange_ ] = str(_app_portrange_).strip().split(":")
   _srcportrange_ = allservice_redefine(_srcportrange_)
   _dstportrange_ = allservice_redefine(_dstportrange_)
   redefined_srcdstportrange_ = str(":".join([ _srcportrange_, _dstportrange_ ]))
   return redefined_srcdstportrange_

def _remove_duplicate_networkvalues_(_netip_list_):
   #
   subnet_tempdict = {}
   for _netip_ in _netip_list_:
      netip_value = _netip_.strip().split(":")[0]
      [ netipaddress, netipsubnet ] = netip_value.strip().split("/")
      if int(netipsubnet) not in subnet_tempdict.keys():
        subnet_tempdict[int(netipsubnet)] = []
      if netip_value not in subnet_tempdict[int(netipsubnet)]:
        subnet_tempdict[int(netipsubnet)].append(netip_value)
   #
   subnet_tempdict_keynames = subnet_tempdict.keys()
   subnet_tempdict_keynames.sort()
   #
   removable_netip_list = []
   #
   listcount = int(0)
   for _subnetvalue_ in subnet_tempdict_keynames:
      for _netip_ in subnet_tempdict[int(_subnetvalue_)]:
         for _bigger_subnetvalue_ in subnet_tempdict_keynames[int(listcount+int(1)):]:
            subneted_netip = list(IPNetwork(_netip_).subnet(int(_bigger_subnetvalue_)))
            for _bigger_netip_ in subnet_tempdict[int(_bigger_subnetvalue_)]:
               if IPNetwork(_bigger_netip_) in subneted_netip:
                 subneted_netip.remove(IPNetwork(_bigger_netip_))
            if not len(subneted_netip):
              if _netip_ not in removable_netip_list:
                removable_netip_list.append(_netip_)
      listcount = listcount + int(1)
   #
   uniqued_netip_list = []
   for _netip_ in _netip_list_:
      remove_status = False
      for rm_netip in removable_netip_list:
         rm_matched_pattern = "^%(rm_netip)s:" % {"rm_netip":rm_netip}
         if re.search(rm_matched_pattern, _netip_, re.I):
           remove_status = True
           break         
      if not remove_status:
        if _netip_ not in uniqued_netip_list:
          uniqued_netip_list.append(_netip_)
   #
   return uniqued_netip_list


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
        # input validation check ! before stating the processing
        ipaddr_pattern = "[0-9]+.[0-9]+.[0-9]+.[0-9]+/[0-9]+"
        _any_portmatching_ = r"(any)/[0-9]+-[0-9]+:[0-9]+-[0-9]+"
        _zero_portmatching_ = r"(0)/[0-9]+-[0-9]+:[0-9]+-[0-9]+"
        _tcp_portmatching_ = r"(tcp)/[0-9]+-[0-9]+:[0-9]+-[0-9]+"
        _udp_portmatching_ = r"(udp)/[0-9]+-[0-9]+:[0-9]+-[0-9]+"
        _icmp_portmatching_ = r"(icmp)"
        _confirmed_input_list_ = []
        for _dictData_ in _input_:
           #
           dictBox_temp = {}
           _keynamelist_ = _dictData_.keys()
           if (u'destinationip' not in _keynamelist_) and (u'sourceip' not in _keynamelist_) and (u'application' not in _keynamelist_):
             return Response(["error, input data has missing information!"], status=status.HTTP_400_BAD_REQUEST)
           #
           if (u'sourceip' not in _keynamelist_):
             _dictData_[u'sourceip'] = u"0.0.0.0/0"
           if (u'destinationip' not in _keynamelist_):
             _dictData_[u'destinationip'] = u"0.0.0.0/0"
           if (u'application' not in _keynamelist_):
             _dictData_[u'application'] = u"0/0-0:0-0"
           #
           _keynamelist_ = _dictData_.keys()
           for _keyname_ in _keynamelist_:
              _items_value_ = _dictData_[_keyname_]
              _expected_netip_value_list_ = str(_items_value_).strip().split(";")
              #
              if re.search('sourceip', str(_keyname_), re.I) or re.search('destinationip', str(_keyname_), re.I):
                for _expected_netip_value_ in _expected_netip_value_list_:
                   if re.match(ipaddr_pattern, str(_expected_netip_value_), re.I):
                     dictBox_temp = _add_stringvalues_into_the_dictionary(_keyname_, dictBox_temp, _expected_netip_value_)
              #
              if re.search('application', str(_keyname_), re.I):
                for _expected_netip_value_ in _expected_netip_value_list_:
                   if re.match(_tcp_portmatching_, str(_expected_netip_value_), re.I) or re.match(_udp_portmatching_, str(_expected_netip_value_), re.I) or re.match(_any_portmatching_, str(_expected_netip_value_), re.I) or re.match(_zero_portmatching_, str(_expected_netip_value_), re.I):
                     dictBox_temp = _add_stringvalues_into_the_dictionary(_keyname_, dictBox_temp, _expected_netip_value_)
                   #
                   searched_icmp_string = re.search(_icmp_portmatching_, str(_expected_netip_value_), re.I)
                   if searched_icmp_string:
                     _icmp_string_ = searched_icmp_string.group(1)
                     dictBox_temp = _add_stringvalues_into_the_dictionary(_keyname_, dictBox_temp, _icmp_string_) 
           #
           _confirmed_input_list_.append(dictBox_temp)
                  

        ## get active devicelist
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
           if (u'apiaccessip' in _keyname_) and (u'failover' in _keyname_) and (u'devicehostname' in _keyname_) or (u'interfaces' in _keyname_) or (u'zonesname' in _keyname_):
             pattern_string = str(_dataDict_[u'failover']).strip()
             if re.match(pattern_string, 'primary', re.I):
               _apiaccessip_ = _dataDict_[u'apiaccessip']
               if _apiaccessip_ not in primarysecondary_devicelist:
                 primarysecondary_devicelist.append(_apiaccessip_)
                 primarysecondary_devicename[_apiaccessip_] = _dataDict_[u"devicehostname"]
                 primarysecondary_interfaces[_apiaccessip_] = _dataDict_[u"interfaces"]
                 primarysecondary_zonesname[_apiaccessip_] = _dataDict_[u"zonesname"]
               

        # get route table information which matched 'primary device' 
        CURL_command = "curl http://0.0.0.0:"+RUNSERVER_PORT+"/juniper/showroute/"
        get_info = os.popen(CURL_command).read().strip()
        stream = BytesIO(get_info)
        data_from_CURL_command = JSONParser().parse(stream)
        routingtable_inmemory = {}
        for _dataDict_ in data_from_CURL_command:
           _keyname_ = _dataDict_.keys()
           for _key_value_ in _keyname_:
              if (unicode(_key_value_) in primarysecondary_devicelist) or (str(_key_value_) in primarysecondary_devicelist):
                routingtable_inmemory[_key_value_] = _dataDict_[_key_value_]

        #
        full_searched_devicelist = []
        for _dictData_ in _confirmed_input_list_:
           #
           source_ip_list = _dictData_[u'sourceip']
           destination_ip_list = _dictData_[u'destinationip']
           # dictbox
           traybox_dict = {}
           traybox_dict[u'sourceip'] = []
           traybox_dict[u'destinationip'] = []
           traybox_dict[u'application'] = []

           # source process and after logest match
           possible_sourceip_list = source_destination_routinglookup(source_ip_list,primarysecondary_devicelist,primarysecondary_devicename,primarysecondary_interfaces,primarysecondary_zonesname,routingtable_inmemory)
           traybox_dict[u'sourceip'] = _remove_duplicate_networkvalues_(logest_matching(possible_sourceip_list))
           #traybox_dict[u'sourceip'] = logest_matching(possible_sourceip_list)

           # destination processing
           possible_destination_list = source_destination_routinglookup(destination_ip_list,primarysecondary_devicelist,primarysecondary_devicename,primarysecondary_interfaces,primarysecondary_zonesname,routingtable_inmemory)
           traybox_dict[u'destinationip'] = _remove_duplicate_networkvalues_(logest_matching(possible_destination_list))
           #traybox_dict[u'destinationip'] = logest_matching(possible_destination_list)

           # application processing
           changed_application = []
           for _expected_ipvalue_ in _dictData_[u'application']:
              #
              _expected_proto_ = ""
              _expected_proto_ = _get_serviceproto_(_any_portmatching_, _expected_ipvalue_, _expected_proto_)
              _expected_proto_ = _get_serviceproto_(_zero_portmatching_, _expected_ipvalue_, _expected_proto_)
              _expected_proto_ = _get_serviceproto_(_tcp_portmatching_, _expected_ipvalue_, _expected_proto_)
              _expected_proto_ = _get_serviceproto_(_udp_portmatching_, _expected_ipvalue_, _expected_proto_)
              _expected_proto_ = _get_serviceproto_(_icmp_portmatching_, _expected_ipvalue_, _expected_proto_)
              #
              if re.match(str("icmp"), _expected_proto_, re.I):
                if str("icmp") not in changed_application:
                  changed_application.append(str("icmp"))
              else:
                redefined_srcdstportrange_ = _redefine_servicerange_(_expected_proto_, _expected_ipvalue_)
                if re.match(str("any"), _expected_proto_, re.I) or re.match(str("0"), _expected_proto_, re.I):
                  redefined_application = "0/%(_prange_)s;tcp/%(_prange_)s;udp/%(_prange_)s;icmp" % {"_prange_":redefined_srcdstportrange_}
                else:
                  redefined_application = "%(_proto_)s/%(_prange_)s" % {"_proto_":str(_expected_proto_).lower(),"_prange_":redefined_srcdstportrange_}
                #
                for _redef_app_ in redefined_application.split(";"):
                   if _redef_app_ not in changed_application:
                     changed_application.append(_redef_app_)
           # 
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

