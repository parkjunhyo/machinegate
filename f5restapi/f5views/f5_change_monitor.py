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
                                 "poolnames" : ["pool names"],
                                 "withssl" : "withssl or withoutssl"
                               },
                               {
                                 "poolnames" : ["p_ICDEc_clapiweb_80"],
                                 "withssl"   : "withoutssl"                    
                               }
                             ]
                  }]

def search_text_in_file(fullpath_filename,_item_value_):
   string_value = str(_item_value_)
   bash_cmd = "cat %(filename)s | grep -i \"%(pattern)s\"" % {"filename":fullpath_filename,"pattern":string_value}
   response_value = os.popen(bash_cmd).read().strip()
   return response_value

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
           for _inputitem_value_ in input_values:
              _inputitem_value_keyname_ = _inputitem_value_.keys()
              if (u'poolnames' not in _inputitem_value_keyname_) or (u'withssl' not in _inputitem_value_keyname_):
                message = "you do not have any valid parameters!"
                return Response(message, status=status.HTTP_400_BAD_REQUEST)

              _matched_dictbox_ = {}
              for _poolname_ in _inputitem_value_[u'poolnames']:
                 _inputitem_string_ = str(_poolname_)
                 match_status = False
                 for _filename_ in listdir_filenames:
                    if re.search("poollist",_filename_,re.I):
                      fullpath_filename = USER_DATABASES_DIR+_filename_                   
                      response_value = search_text_in_file(fullpath_filename,_inputitem_string_)
                      if len(response_value):
                        stream = BytesIO(response_value)
                        response_json = JSONParser().parse(stream)
                        for _item_in_ in response_json[u'items']:
                           if re.match(_inputitem_string_,str(_item_in_[u'name']).strip(),re.I):
                             matched_keyname = _matched_dictbox_.keys()
                             if _inputitem_string_ not in matched_keyname:
                               _matched_dictbox_[_inputitem_string_] = {}
                               _matched_dictbox_[_inputitem_string_]['monitor'] = str(_item_in_[u'monitor'])
                               _temp_iplist_ = _filename_.strip().split(".")
                               ipaddress = str(".".join(_temp_iplist_[1:(len(_temp_iplist_)-1)]))
                               _matched_dictbox_[_inputitem_string_]['activedevice'] = active_device_ip(ipaddress)
                             match_status = True 
                 if not match_status:
                   message = "input value does not has proper format!!"
                   return Response(message, status=status.HTTP_400_BAD_REQUEST) 
              _matched_input_values_.append(_matched_dictbox_)

           return_command = []
           for _DictData_ in _matched_input_values_:
              _DictData_keyname_ = _DictData_.keys()
              for _keyname_ in _DictData_keyname_:

                 # find out the option
                 option_value = False
                 for _inputitem_value_ in input_values:
                    if not option_value:
                      for _poolname_ in _inputitem_value_[u'poolnames']:
                         if re.match(str(_keyname_),str(_poolname_),re.I):
                           option_value = str(_inputitem_value_[u'withssl'])

                 _activedevice_ = _DictData_[_keyname_]['activedevice']
                 for _monitor_ in DEFAULT_MONITOR:
                    if _activedevice_ in _monitor_["device"]:
                      monitor_change_value = _monitor_['monitor'][option_value]
                      break

                 # monitor origin
                 monitor_origin = _DictData_[_keyname_]['monitor']

                 # create command
                 templates = {}
                 templates["exchangecmd"] =  DEFAULT_MONITOR_CURL_STRING % {"USER_NAME":USER_NAME,"USER_PASSWORD":USER_PASSWORD,"_DEVICE_IP_":_activedevice_,"_POOLNAME_":_keyname_,"_MONITOR_":monitor_change_value}
                 templates["origincmd"] = DEFAULT_MONITOR_CURL_STRING % {"USER_NAME":USER_NAME,"USER_PASSWORD":USER_PASSWORD,"_DEVICE_IP_":_activedevice_,"_POOLNAME_":_keyname_,"_MONITOR_":monitor_origin}
                 return_command.append(templates)

        return Response(return_command)

      except:
        message = "post algorithm has some problem!"
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

