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

def transfer_crul_to_get_virtualserver_info(_DEVICE_IP_):

    # clean up database file
    database_filename = USER_DATABASES_DIR+"virtualserverlist."+_DEVICE_IP_+".txt"
    f = open(database_filename,"w")
    f.close()

    # send curl message
    CURL_command = "curl -sk -u "+USER_NAME+":"+USER_PASSWORD+" https://"+_DEVICE_IP_+"/mgmt/tm/ltm/virtual/ -H 'Content-Type: application/json'"
    get_info = os.popen(CURL_command).read().strip()
    f = open(database_filename,"w")
    f.write(get_info)
    f.close()
    
    # threading must have
    time.sleep(0)

def get_virtualserverlist_name(_FILENAME_):
    f = open(USER_DATABASES_DIR+_FILENAME_,"r")
    _contents_ = f.readlines()
    f.close()

    stream = BytesIO(_contents_[0])
    data_from_file = JSONParser().parse(stream)

    _combination_ = {}
    for _dict_Data_ in data_from_file["items"]:
       _combination_[str(_dict_Data_["fullPath"])] = str(_dict_Data_["destination"])
    # return dictionary value
    return _combination_


@api_view(['GET','POST'])
@csrf_exempt
def f5_virtualserverlist(request,format=None):

   # get method
   if request.method == 'GET':

      _contents_in_ = []
      fileindatabasedir = os.listdir(USER_DATABASES_DIR)
      for _filename_ in fileindatabasedir:
         if re.search("virtualserverlist.[0-9]+.[0-9]+.[0-9]+.[0-9]+.txt",_filename_):
            _contents_in_.append(get_virtualserverlist_name(_filename_))
      # return value 
      return Response(_contents_in_)


   elif request.method == 'POST':

      try:
        _input_ = JSONParser().parse(request)
        if re.match(ENCAP_PASSWORD,str(_input_[0]['auth_key'])):

           # log message
           f = open(LOG_FILE,"a")
           _date_ = os.popen("date").read().strip()
           log_msg = _date_+" from : "+request.META['REMOTE_ADDR']+" , method POST request to run f5_virtualserverlist function!\n"
           f.write(log_msg)
           f.close()

           # read db file
           _devicelist_db_ = USER_DATABASES_DIR + "devicelist.txt"
           f = open(_devicelist_db_,'r')
           _string_contents_ = f.readlines()
           f.close()
           stream = BytesIO(_string_contents_[0])
           _data_from_devicelist_db_= JSONParser().parse(stream)

           # standby server list
           standby_device_list = []           
           for _dict_information_ in _data_from_devicelist_db_:
              if re.match('standby',str(_dict_information_[u'failover'])):
                 if str(_dict_information_[u'ip']) not in standby_device_list:
                    standby_device_list.append(str(_dict_information_[u'ip']))

           # send curl command to device
           _threads_ = []
           for _ip_address_ in standby_device_list:
              th = threading.Thread(target=transfer_crul_to_get_virtualserver_info, args=(_ip_address_,))
              th.start()
              _threads_.append(th)
           for th in _threads_:
              th.join()

           # get the result data
           _contents_in_ = []
           fileindatabasedir = os.listdir(USER_DATABASES_DIR)
           for _filename_ in fileindatabasedir:
               if re.search("virtualserverlist.[0-9]+.[0-9]+.[0-9]+.[0-9]+.txt",_filename_):
                  _contents_in_.append(get_virtualserverlist_name(_filename_))
            
           message = _contents_in_
           return Response(message)


      except:
        message = ["need information to activate"]
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

