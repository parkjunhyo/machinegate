from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.renderers import JSONRenderer
from rest_framework.parsers import JSONParser

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils.six import BytesIO

import os,re,copy,json,threading,time,sys

from f5restapi.setting import LOG_FILE
from f5restapi.setting import USER_DATABASES_DIR 
from f5restapi.setting import USER_NAME,USER_PASSWORD
from f5restapi.setting import ENCAP_PASSWORD
from f5restapi.setting import THREAD_TIMEOUT
from f5restapi.setting import RUNSERVER_PORT


class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders its content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)

DEFAULT_MONITOR = [
                   {
                    "device":["10.10.77.29","10.10.77.30","10.10.77.45","10.10.77.46","10.10.30.101","10.10.30.102"],
                    "monitor":{
                                  "withssl":"https_healthcheck.jsp_skphok",
                                  "withoutssl":"http_healthcheck.jsp_skphok"
                              }
                   },
                   {
                    "device":["10.10.77.31","10.10.77.32","10.10.77.33","10.10.77.34"],
                    "monitor":{
                                  "withssl":"tcp_skp",
                                  "withoutssl":"tcp_skp"
                              }
                   }
                  ]

DEFAULT_MONITOR_CURL_STRING = "curl -sk -u %(USER_NAME)s:%(USER_PASSWORD)s https://%(_DEVICE_IP_)s/mgmt/tm/ltm/pool/%(_POOLNAME_)s -X PUT -d '{\"monitor\":\"%(_MONITOR_)s\"}' -H 'Content-Type: application/json'"

getview_message = [{
                     "items":[
                               {
                                 "device" : "KRIS10-DMZS01-5000L4.skplanet.com",
                                 "withssl" : ["p_ICDEc_clapiweb_80"],
                                 "withoutssl" : []
                               }
                             ]
                  }]

#def search_text_in_file(fullpath_filename,_item_value_):
#   string_value = str(_item_value_)
#   bash_cmd = "cat %(filename)s | grep -i \"%(pattern)s\"" % {"filename":fullpath_filename,"pattern":string_value}
#   response_value = os.popen(bash_cmd).read().strip()
#   return response_value

def active_device_ip(ipaddress):
   ip_address = str(ipaddress)
   devicedbfile = USER_DATABASES_DIR+"devicelist.txt"
   f = open(devicedbfile,'r')
   _read_contents_ = f.readlines()
   f.close()
   stream = BytesIO(_read_contents_[0])
   response_json = JSONParser().parse(stream)
   haclustername = False
   for _dict_ in response_json:
      if re.search(ip_address,str(_dict_[u'ip']),re.I):
        if re.match("active",str(_dict_[u'failover']),re.I):
          active_device = str(ip_address)
          return active_device
        else:
          haclustername = str(_dict_[u'haclustername'])
   
   if haclustername:     
      for _dict_ in response_json:
         if re.search(haclustername,str(_dict_[u'clustername']),re.I):
           if re.match("active",str(_dict_[u'failover']),re.I):
             active_device = str(_dict_[u'ip'])
             return active_device

@api_view(['GET','POST'])
@csrf_exempt
def f5_change_monitor(request,format=None):

   # get method
   if request.method == 'GET':
      return Response(getview_message)

   elif request.method == 'POST':

      try:

        _input_ = JSONParser().parse(request)

        if u'auth_key' not in _input_[0].keys():
           message = "you do not have permission to use this service!"
           return Response(message, status=status.HTTP_400_BAD_REQUEST)

        if (u'items' not in _input_[0].keys()) or (len(_input_[0][u'items']) == int(0)):
           message = "you do not have any valid input!"
           return Response(message, status=status.HTTP_400_BAD_REQUEST)
          
        input_encap_password = str(_input_[0][u'auth_key'])
        input_values = _input_[0][u'items']


        if re.match(input_encap_password,ENCAP_PASSWORD):

           listdir_filenames = os.listdir(USER_DATABASES_DIR)

           _matched_input_values_ = []
           return_command = []
           for _inputitem_value_ in input_values:
              _inputitem_value_keyname_ = _inputitem_value_.keys()

              if (u'device' not in _inputitem_value_keyname_):
                message = "you do not have any valid parameters!"
                return Response(message, status=status.HTTP_400_BAD_REQUEST)

              going_status = False
              if (u'withssl' in _inputitem_value_keyname_) or (u'withoutssl' in _inputitem_value_keyname_):
                going_status = True

              if not going_status:
                message = "you do not have any valid parameters!"
                return Response(message, status=status.HTTP_400_BAD_REQUEST)

              curl_command = "curl http://0.0.0.0:"+RUNSERVER_PORT+"/f5/devicelist/"
              get_info = os.popen(curl_command).read().strip()
              stream = BytesIO(get_info)
              _dictdata_ = JSONParser().parse(stream)

              _input_devicename_ = str(_inputitem_value_[u'device'])
              
              matched_ip = None
              for _devicedict_ in _dictdata_:
                 if re.search(_input_devicename_,str(_devicedict_[u'devicehostname']),re.I) or re.search(_input_devicename_,str(_devicedict_[u'clustername']),re.I):
                   #if re.search(str(u'active'),str(_devicedict_[u'failover']),re.I):
                   matched_ip = str(_devicedict_[u'ip'])
              if not matched_ip:
                message = "device name is not proper!"
                return Response(message, status=status.HTTP_400_BAD_REQUEST) 
              matched_active_ip = active_device_ip(matched_ip)
          
              matched_standby_ip = None
              for _devicedict_ in _dictdata_:
                 if re.search(matched_active_ip,str(_devicedict_[u'ip']),re.I):
                   ha_host_name = str(_devicedict_[u'haclustername'])
                   for _loop2_ in _dictdata_:
                      if re.search(ha_host_name,str(_loop2_[u'clustername']),re.I):
                        matched_standby_ip = str(_loop2_[u'ip'])


              curl_command = "curl http://0.0.0.0:"+RUNSERVER_PORT+"/f5/poolmemberlist/"
              get_info = os.popen(curl_command).read().strip()
              stream = BytesIO(get_info)
              _dictdata_ = JSONParser().parse(stream)


              poolmembrlist_key = _dictdata_.keys()
              matched_key_ipaddress = None
              for _ipaddress_ in poolmembrlist_key:
                _ipaddress_string_ = str(_ipaddress_)
                if _ipaddress_string_ in [matched_active_ip, matched_standby_ip]:
                  matched_key_ipaddress = _ipaddress_string_

              if not matched_key_ipaddress:
                message = "no database of the input device host"
                return Response(message, status=status.HTTP_400_BAD_REQUEST)

              matched_database_poolmemberlist = _dictdata_[unicode(matched_key_ipaddress)]
              matched_database_poolmemberlist_keyname = matched_database_poolmemberlist.keys()
                 

              ## input value initialization
              _inputitem_value_keynames_ = _inputitem_value_.keys()
              if u'withssl' in _inputitem_value_keynames_:
                _input_withssl_poolnamelist_ = _inputitem_value_[u'withssl']
              else:
                _input_withssl_poolnamelist_ = []

              if u'withoutssl' in _inputitem_value_keynames_:
                _input_withoutssl_poolnamelist_ = _inputitem_value_[u'withoutssl']
              else:
                _input_withoutssl_poolnamelist_ = []

              ## create the curl command
              recursive_value = {"withssl":_input_withssl_poolnamelist_,"withoutssl":_input_withoutssl_poolnamelist_}
              for _keyname_ in recursive_value.keys():
                 for _poolname_ in recursive_value[_keyname_]:

                    change_monitor_value = None
                    for _dictvalue_ in DEFAULT_MONITOR:
                       if matched_key_ipaddress in _dictvalue_["device"]:
                         change_monitor_value = _dictvalue_["monitor"][_keyname_]
                    if not change_monitor_value:
                      message = "no defined monitor information to %(_keyname_)s" % {"_keyname_":str(_keyname_)}
                      return Response(message, status=status.HTTP_400_BAD_REQUEST)

                    _poolname_string_ = str(_poolname_) 
                    origin_monitor = None
                    for _keyname_loop2_ in matched_database_poolmemberlist_keyname:
                       _poolname_indb_ = str(_keyname_loop2_) 
                       if re.search(_poolname_string_,_poolname_indb_,re.I):
                         origin_monitor = matched_database_poolmemberlist[_keyname_loop2_][u'monitors']                 
                    if not origin_monitor:
                      message = "[ %(poolname)s ] is not on the [ %(ipaddress)s ] device!" % {"poolname":_poolname_string_,"ipaddress":matched_standby_ip}
                      return Response(message, status=status.HTTP_400_BAD_REQUEST)

                    templates = {}
                    templates["exchangecmd"] =  DEFAULT_MONITOR_CURL_STRING % {"USER_NAME":USER_NAME,"USER_PASSWORD":USER_PASSWORD,"_DEVICE_IP_":matched_active_ip,"_POOLNAME_":_poolname_indb_,"_MONITOR_":change_monitor_value}
                    templates["origincmd"] = DEFAULT_MONITOR_CURL_STRING % {"USER_NAME":USER_NAME,"USER_PASSWORD":USER_PASSWORD,"_DEVICE_IP_":matched_active_ip,"_POOLNAME_":_poolname_indb_,"_MONITOR_":origin_monitor}
                    return_command.append(templates)

        return Response(return_command)

      except:
        message = "post algorithm has some problem!"
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

