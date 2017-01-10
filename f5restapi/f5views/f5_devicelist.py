from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.renderers import JSONRenderer
from rest_framework.parsers import JSONParser

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils.six import BytesIO

import os,re,copy,json

from f5restapi.setting import LOG_FILE
from f5restapi.setting import USER_DATABASES_DIR 
from f5restapi.setting import USER_NAME,USER_PASSWORD
from f5restapi.setting import ENCAP_PASSWORD

class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders its content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)


@api_view(['GET','POST'])
@csrf_exempt
def f5_devicelist(request,format=None):

   devicelist_file = USER_DATABASES_DIR + "devicelist.txt"
   
   # get method
   if request.method == 'GET':
      try:

         f = open(devicelist_file,"r")
         string_content = f.readlines()
         f.close()

         # converter string to dict
         stream = BytesIO(string_content[0])
         data_from_databasefile = JSONParser().parse(stream)

         # return
         return Response(data_from_databasefile)  

      except:
         message = ["device list database is not existed!"]
         return Response(message, status=status.HTTP_400_BAD_REQUEST)


   elif request.method == 'POST':

      try:
        _input_ = JSONParser().parse(request)

        if re.match(ENCAP_PASSWORD,str(_input_[0]['auth_key'])):

           # log message
           f = open(LOG_FILE,"a")
           _date_ = os.popen("date").read().strip()
           log_msg = _date_+" from : "+request.META['REMOTE_ADDR']+" , method POST request to run f5_devicelist function!\n"
           f.write(log_msg)
           f.close()

           # read database file to lookup ip
           f = open(devicelist_file,"r")
           string_content = f.readlines()
           f.close()

           # get from database file
           stream = BytesIO(string_content[0].strip())
           data_from_databasefile = JSONParser().parse(stream)

           # init database file
  #         f = open(devicelist_file,"w")
  #         f.close()

           # update database file
           message = []
           for _param_ in data_from_databasefile:

              # ip information
              if not re.match("[0-9]+.[0-9]+.[0-9]+.[0-9]+",str(_param_['ip']).strip()):
                 message = ["device list database is not normal, please check the device database file!"]
                 return Response(message, status=status.HTTP_400_BAD_REQUEST)

              curl_command = "curl -sk -u "+USER_NAME+":"+USER_PASSWORD+" https://"+str(_param_['ip']).strip()+"/mgmt/tm/cm/device -H 'Content-Type: application/json'"
              _response_ = os.popen(curl_command).read().strip()
              stream = BytesIO(_response_)
              data_from_response = JSONParser().parse(stream)


              _result_dict_ = {} 
              for _dictData_ in data_from_response[u'items']:
                 if re.match(str(_dictData_[u'managementIp']),str(_param_['mgmtip']).strip()):
                 #if re.match(str(_dictData_[u'managementIp']),str(_param_['ip']).strip()):
                    _result_dict_["failover"] = str(_dictData_[u'failoverState'])
                    _result_dict_["clustername"] = str(_dictData_[u'name'])
                    _result_dict_["devicehostname"] = str(_dictData_[u'hostname'])
                    #_result_dict_["ip"] = str(_dictData_[u'managementIp'])
                    _result_dict_["ip"] = str(_param_['ip']).strip()
                    _result_dict_["mgmtip"] = str(_dictData_[u'managementIp']) 
     

              # interface information
              curl_command = "curl -sk -u "+USER_NAME+":"+USER_PASSWORD+" https://"+_result_dict_["ip"].strip()+"/mgmt/tm/net/interface -H 'Content-Type: application/json'"
              raw_data= os.popen(curl_command).read().strip()
              stream = BytesIO(raw_data)
              data_forinterface_from_request = JSONParser().parse(stream)
              cache_interface = {}
              for _target_ in data_forinterface_from_request[u'items']:
                 _interfacename_ = _target_[u"name"]
                 if (u"enabled" in _target_.keys()) or ("enabled" in _target_.keys()):
                   if _target_[u"enabled"] or re.search("true", str(_target_[u"enabled"]).strip(), re.I):
                     if _interfacename_ not in cache_interface.keys():
                       cache_interface[_interfacename_] = {}
                       cache_interface[_interfacename_][u"name"] = _interfacename_
                       cache_interface[_interfacename_][u"portstatus"] = "enable"
                       cache_interface[_interfacename_][u"macAddress"] = _target_[u"macAddress"]
                       cache_interface[_interfacename_][u"mediaMax"]= _target_[u"mediaMax"] 
               
              # trunk information
              curl_command = "curl -sk -u "+USER_NAME+":"+USER_PASSWORD+" https://"+_result_dict_["ip"].strip()+"/mgmt/tm/net/trunk -H 'Content-Type: application/json'"
              raw_data= os.popen(curl_command).read().strip()
              stream = BytesIO(raw_data)
              data_fortrunk_from_request = JSONParser().parse(stream)
              cache_trunk = {}
              for _target_ in data_fortrunk_from_request[u'items']:
                 _trunkname_ = _target_[u"name"]
                 temp_listbox = []
                 for _interfacename_ in _target_[u"interfaces"]:
                    if _interfacename_ in cache_interface.keys():
                      temp_listbox.append(cache_interface[_interfacename_])
                 if len(temp_listbox):
                   cache_trunk[_trunkname_] = {}
                   cache_trunk[_trunkname_][u"name"] = _trunkname_
                   cache_trunk[_trunkname_][u"macAddress"] = _target_[u"macAddress"]
                   cache_trunk[_trunkname_][u"lacp"] = _target_[u"lacp"]
                   cache_trunk[_trunkname_][u"lacpMode"] = _target_[u"lacpMode"]
                   cache_trunk[_trunkname_][u"interfaces"] = temp_listbox  
                
              # vlan information
              curl_command = "curl -sk -u "+USER_NAME+":"+USER_PASSWORD+" https://"+_result_dict_["ip"].strip()+"/mgmt/tm/net/vlan -H 'Content-Type: application/json'"
              raw_data= os.popen(curl_command).read().strip()
              stream = BytesIO(raw_data)
              data_forvlan_from_request = JSONParser().parse(stream)
              cache_vlan = {}
              for _target_ in data_forvlan_from_request[u'items']:
                 _vlanname_ = _target_[u"name"]
                 curl_command = "curl -sk -u "+USER_NAME+":"+USER_PASSWORD+" https://"+_result_dict_["ip"].strip()+"/mgmt/tm/net/vlan/~Common~"+str(_vlanname_)+"/interfaces -H 'Content-Type: application/json'"
                 raw_data= os.popen(curl_command).read().strip()
                 stream = BytesIO(raw_data)
                 vlaninterface_data = JSONParser().parse(stream)
                 temp_listbox = []
                 for _values_inner_dict_ in vlaninterface_data[u'items']:
                    if _values_inner_dict_[u"name"] in cache_trunk.keys():
                      temp_listbox.append(cache_trunk[_values_inner_dict_[u"name"]])
                    if _values_inner_dict_[u"name"] in cache_interface.keys():
                      temp_listbox.append(cache_interface[_values_inner_dict_[u"name"]])
                 if len(temp_listbox):
                   cache_vlan[_vlanname_] = {}
                   cache_vlan[_vlanname_][u"name"] = _vlanname_
                   cache_vlan[_vlanname_][u"interfaces"] = temp_listbox
                   cache_vlan[_vlanname_][u"tag"] = _target_[u"tag"]
 
                    
              # self information
              curl_command = "curl -sk -u "+USER_NAME+":"+USER_PASSWORD+" https://"+_result_dict_["ip"].strip()+"/mgmt/tm/net/self -H 'Content-Type: application/json'"
              raw_data= os.popen(curl_command).read().strip()
              stream = BytesIO(raw_data)
              data_forself_from_request = JSONParser().parse(stream)
              temp_listbox = {}
              for _target_ in data_forself_from_request[u'items']:
                 _vlanstring_ = str(str(_target_[u"vlan"]).strip().split("/")[-1])
                 if (unicode(_vlanstring_) in cache_vlan.keys()) or (_vlanstring_ in cache_vlan.keys()):
                   _ipvalues_ = _target_[u"address"] 
                   if _ipvalues_ not in temp_listbox.keys():
                     temp_listbox[_ipvalues_] = {}
                   temp_listbox[_ipvalues_][u"floating"] = _target_[u"floating"]
                   temp_listbox[_ipvalues_][u"vlan"] = cache_vlan[unicode(_vlanstring_)]
              _result_dict_["ipaddress"] = temp_listbox

              # cluster information 
              curl_command = "curl -sk -u "+USER_NAME+":"+USER_PASSWORD+" https://"+_result_dict_["ip"].strip()+"/mgmt/tm/cm/trust-domain -H 'Content-Type: application/json'"
              raw_data= os.popen(curl_command).read().strip()
              stream = BytesIO(raw_data)
              data_from_response = JSONParser().parse(stream)

              _temp_list_ = []
              for _target_ in data_from_response[u'items']:
                  for _caDevices_ in _target_[u'caDevices']:
                      _Dname_ = _caDevices_.strip().split('/')[-1]
                      if not re.match(str(_Dname_),str(_result_dict_["clustername"])):
                         _temp_list_.append(str(_Dname_))
              _result_dict_["haclustername"] = _temp_list_[-1]

              # find device-group
              curl_command = "curl -sk -u "+USER_NAME+":"+USER_PASSWORD+" https://"+_result_dict_["ip"].strip()+"/mgmt/tm/cm/device-group -H 'Content-Type: application/json'"
              raw_data= os.popen(curl_command).read().strip()
              stream = BytesIO(raw_data)
              data_from_response = JSONParser().parse(stream)
 
              for _target_ in data_from_response[u'items']:
                 if re.search(str(_target_[u'type']),str('sync-failover')):
                    _result_dict_["devicegroupname"] = str(_target_[u'name'])

              # result add
              message.append(_result_dict_)
           # return and update database file
           f = open(devicelist_file,"w")
           f.write(json.dumps(message))
           f.close()
           return Response(message)


      except:
        message = [{}]
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

