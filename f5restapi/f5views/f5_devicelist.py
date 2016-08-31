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
     
              # curl message command
              #curl_command = "curl -sk -u "+USER_NAME+":"+USER_PASSWORD+" https://"+str(_param_['ip']).strip()+"/mgmt/tm/sys/failover -H 'Content-Type: application/json'"

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

