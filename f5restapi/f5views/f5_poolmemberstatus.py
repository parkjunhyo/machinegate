from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.renderers import JSONRenderer
from rest_framework.parsers import JSONParser

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils.six import BytesIO

import os,re,copy,json,threading,time

from f5restapi.setting import LOG_FILE
from f5restapi.setting import USER_DATABASES_DIR 
from f5restapi.setting import USER_NAME,USER_PASSWORD
from f5restapi.setting import ENCAP_PASSWORD
from f5restapi.setting import THREAD_TIMEOUT

class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders its content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)


@api_view(['GET'])
@csrf_exempt
def f5_poolmemberstatus(request,poolname,format=None):

   # get method
   if request.method == 'GET':
      try:
         fileindatabasedir = os.listdir(USER_DATABASES_DIR)
         _matched_all_ = {}
         for _filename_ in fileindatabasedir:
            if re.search("virtualserverlist.[0-9]+.[0-9]+.[0-9]+.[0-9]+.txt",_filename_):

               f = open(USER_DATABASES_DIR+_filename_,"r")
               _contents_ = f.readlines()
               f.close()
               stream = BytesIO(_contents_[0])
               data_from_file = JSONParser().parse(stream)
            
               for _dict_Data_ in data_from_file["items"]:
                   if u'pool' in _dict_Data_.keys() or str(u'pool') in _dict_Data_.keys():
                      if re.match(_dict_Data_[u'name'],poolname.strip()) or re.match(_dict_Data_[u'pool'].strip().split('/')[-1],poolname.strip()):
                         _matched_all_[str(re.search("[0-9]+.[0-9]+.[0-9]+.[0-9]+",_filename_).group(0))] = _dict_Data_[u'pool'].strip().split('/')[-1] 

         devicelist_file = USER_DATABASES_DIR + "devicelist.txt"
         f = open(devicelist_file,"r")
         _contents_ = f.readlines()
         f.close()
         stream = BytesIO(_contents_[0])
         data_from_file = JSONParser().parse(stream)

         _standby_list_ = []
         _device_list_ = {}
         for _dict_Data_ in data_from_file:
             _device_list_[str(_dict_Data_[u'ip'])] = _dict_Data_[u'name'] 
             if (_dict_Data_[u'ip'] in _matched_all_.keys() or _dict_Data_[str(u'ip')] in _matched_all_.keys()) and (re.match(_dict_Data_[u'failover'],'standby') or re.match(_dict_Data_[str(u'failover')],'standby')):
                _standby_list_.append(str(_dict_Data_[u'ip']))
    
         _status_all_ = {} 
         for _standby_ip_ in _standby_list_:
             CURL_command = "curl -sk -u "+USER_NAME+":"+USER_PASSWORD+" https://"+_standby_ip_+"/mgmt/tm/ltm/pool/"+_matched_all_[_standby_ip_]+"/members/ -H 'Content-Type: application/json'"
             get_info = os.popen(CURL_command).read().strip()
             stream = BytesIO(get_info)
             data_from_file = JSONParser().parse(stream)

             _member_status_ = {}
             for _dict_Data_ in data_from_file[u'items']:
                 _member_status_[str(_dict_Data_[u'name'])] = str(_dict_Data_[u'state'])
             _status_all_[_matched_all_[str(_standby_ip_)]] = _member_status_
             _status_all_[str(_standby_ip_)] = _device_list_[str(_standby_ip_)]
      except:
         _status_all_ = {} 
         message = _status_all_
         return Response(message)


      # get the result data and return
      message = _status_all_
      return Response(message)

