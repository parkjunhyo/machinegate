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

def compare_srcdstapplist(srclist,dstlist,applist):
   set_srclist = set(srclist)
   set_dstlist = set(dstlist)
   set_applist = set(applist)
   compare_srcdst = set_srclist.intersection(dstlist)
   compare_dstsrc = set_dstlist.intersection(srclist)
   if compare_srcdst == compare_dstsrc:
     compare_srcdstapp = compare_srcdst.intersection(applist)
     compare_appsrcdst = set_applist.intersection(list(compare_srcdst))
     if compare_srcdstapp == compare_appsrcdst:
       templist_box = []
       for _common_ in list(compare_srcdstapp):
          if str(_common_) not in templist_box:
            templist_box.append(str(_common_)) 
     else:
       return Response("error, application compare has issue!", status=status.HTTP_400_BAD_REQUEST)
   else:
     return Response("error, source and destination compare has issue!", status=status.HTTP_400_BAD_REQUEST)
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
     

@api_view(['GET','POST'])
@csrf_exempt
def juniper_searchpolicy(request,format=None):

   # get method
   if request.method == 'GET':
      try:
         get_message = [
           {
             "sourceip" : "172.22.113.10/32;172.22.113.11/32",
             "destinationip" : "172.22.208.15/32",
             "application" : "tcp/1700;tcp/443"
           },
           {
             "sourceip" : "172.22.0.0/16",
             "destinationip" : "172.22.209.0/24",
             "application" : "icmp-all/0"
           },
           {
             "sourceip" : "172.22.112.0/23",
             "destinationip" : "172.22.208.10/28",
             "application" : "any/0"
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
        #

        CURL_command = "curl -H \"Accept: application/json\" -X POST -d \'"+json.dumps(_input_)+"\' http://0.0.0.0:"+RUNSERVER_PORT+"/juniper/searchzonefromroute/"
        get_info = os.popen(CURL_command).read().strip()
        stream = BytesIO(get_info)
        data_from_CURL_command = JSONParser().parse(stream)
 
        return_list_temp = []
        for _dictData_ in data_from_CURL_command:
           for _src_string_ in _dictData_[u"sourceip"]:
              [ inputsrc_netip, inputsrc_device, inputsrc_zone ] = parsing_filename_to_data(_routing_dict_,_src_string_)
              for _dst_value_ in _dictData_[u"destinationip"]:
                 [ inputdst_netip, inputdst_device, inputdst_zone ] = parsing_filename_to_data(_routing_dict_,_dst_value_) 
                 if not re.match(inputsrc_device, inputdst_device, re.I):
                   return Response(["error, search zone from routing table has issue!"], status=status.HTTP_400_BAD_REQUEST) 
                 for _app_value_ in _dictData_[u"application"]:       
                    # initialization the container
                    tempdict_box = {}
                    # any rule define
                    appvalue_string = _app_value_.strip().split("/")
                    if len(appvalue_string) != int(2):
                      return Response("error, application : any is wrong format!", status=status.HTTP_400_BAD_REQUEST)
                    [ _app_proto_, _app_number_ ] = appvalue_string
                    if re.search("any",_app_proto_.lower(),re.I):
                      _app_value_ = "0/0"
                    policy_cache_filename = "cachepolicy_%(_devicestring_)s_from_%(_fromzone_)s_to_%(_tozone_)s.txt" % {"_devicestring_":str(inputsrc_device),"_fromzone_":str(inputsrc_zone),"_tozone_":str(inputdst_zone)}

                    # fill default container
                    tempdict_box[u'sourceip'] = str(inputsrc_netip)
                    tempdict_box[u'destinationip'] = str(inputdst_netip)
                    tempdict_box[u'application'] = str(_app_value_)
                    tempdict_box[u'devicename'] = str(inputsrc_device)
                    tempdict_box[u'fromzone'] = str(inputsrc_zone)
                    tempdict_box[u'tozone'] = str(inputdst_zone)
                    tempdict_box[u'matchedpolicy'] = []
                    tempdict_box[u'matchproperity'] = str("none")

                    # first find policy from database perfect match!
                    maching_policy_status = False

                    if str(policy_cache_filename) in cache_filename:
                      # file db read
                      database_filefull = USER_VAR_CHCHES + str(policy_cache_filename) 
                      f = open(database_filefull,"r")
                      string_contents = f.readlines()
                      f.close()
                      stream = BytesIO(string_contents[0])
                      file_database = JSONParser().parse(stream)
                      
                      source_in_filedb_list = []
                      destination_in_filedb_list = []
                      application_in_filedb_list = []
                      source_in_filedb_list  = get_listvalue_matchedby_keyname(file_database[u'source'],inputsrc_netip)
                      destination_in_filedb_list  = get_listvalue_matchedby_keyname(file_database[u'destination'],inputdst_netip)
                      application_in_filedb_list = get_listvalue_matchedby_keyname(file_database[u'application'],_app_value_)
                      if len(source_in_filedb_list)*len(destination_in_filedb_list)*len(application_in_filedb_list):
                        # there is something matched in the cache
                        matched_policylist = []
                        matched_policylist = compare_srcdstapplist(source_in_filedb_list,destination_in_filedb_list,application_in_filedb_list)
                        if len(matched_policylist) != 0:
                          tempdict_box[u'matchedpolicy'] = matched_policylist
                          tempdict_box[u'matchproperity'] = str("perfectmatch")
                          maching_policy_status = True

                    # second find policy from database include match!
                    if not maching_policy_status:
                      source_in_filedb_list = []
                      destination_in_filedb_list = []
                      application_in_filedb_list = []
                      source_in_filedb_list = compare_including_netip(file_database[u'source'],inputsrc_netip)
                      destination_in_filedb_list = compare_including_netip(file_database[u'destination'],inputdst_netip)
                      application_in_filedb_list = get_listvalue_matchedby_keyname(file_database[u'application'],_app_value_)
                      if len(source_in_filedb_list)*len(destination_in_filedb_list)*len(application_in_filedb_list):
                        matched_policylist = []
                        matched_policylist = compare_srcdstapplist(source_in_filedb_list,destination_in_filedb_list,application_in_filedb_list)
                        if len(matched_policylist) != 0:
                          tempdict_box[u'matchedpolicy'] = matched_policylist 
                          tempdict_box[u'matchproperity'] = str("includematch")
                          maching_policy_status = True

                    # third find policy from database include match! partial_includ_match_netip
                    if not maching_policy_status:
                      source_in_filedb_list = []
                      destination_in_filedb_list = []
                      application_in_filedb_list = []
                      source_in_filedb_list = partial_includ_match_netip(file_database[u'source'],inputsrc_netip)
                      destination_in_filedb_list = partial_includ_match_netip(file_database[u'destination'],inputdst_netip)
                      application_in_filedb_list = get_listvalue_matchedby_keyname(file_database[u'application'],_app_value_)
                      if len(source_in_filedb_list)*len(destination_in_filedb_list)*len(application_in_filedb_list):
                        matched_policylist = []
                        matched_policylist = compare_srcdstapplist(source_in_filedb_list,destination_in_filedb_list,application_in_filedb_list)
                        if len(matched_policylist) != 0:
                          tempdict_box[u'matchedpolicy'] = matched_policylist
                          tempdict_box[u'matchproperity'] = str("partialmatch")
                          maching_policy_status = True
                      
                    # add the container
                    return_list_temp.append(tempdict_box)
        
        return Response(return_list_temp)

      except:
        message = "Post Algorithm has some problem!"
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

