from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.renderers import JSONRenderer
from rest_framework.parsers import JSONParser

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils.six import BytesIO

import os,re,copy,json,threading,time,subprocess

from f5restapi.setting import LOG_FILE
from f5restapi.setting import USER_DATABASES_DIR 
from f5restapi.setting import USER_NAME,USER_PASSWORD
from f5restapi.setting import ENCAP_PASSWORD
from f5restapi.setting import RUNSERVER_PORT
from f5restapi.setting import THREAD_TIMEOUT


class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders its content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)


def get_snatranslation_info(_database_target_):

   CURL_command = "curl -sk -u "+USER_NAME+":"+USER_PASSWORD+" https://"+_database_target_+"/mgmt/tm/ltm/snat/ -H 'Content-Type: application/json'"
   get_info = os.popen(CURL_command).read().strip()
   stream = BytesIO(get_info)
   data_from_CURL_command = JSONParser().parse(stream)
   
   # create db file
   f = open(USER_DATABASES_DIR+"snatranslationlist."+_database_target_+".txt","w")
   f.write(json.dumps(data_from_CURL_command))
   f.close()

   # threading must have
   time.sleep(0)

def show_snatranslation_filedb(standby_device_list):

   fileindatabasedir = os.listdir(USER_DATABASES_DIR) 

   # file existed check
   filestatus = False
   filepattern = "snatranslationlist.[0-9]+.[0-9]+.[0-9]+.[0-9]+.txt"
   for _filename_ in fileindatabasedir:
      if re.search(filepattern,_filename_,re.I):
        filestatus = True
        break

   if not filestatus:
     CURL_command = "curl -H \"Accept: application/json\" -X POST -d \'[{\"auth_key\":\""+ENCAP_PASSWORD+"\"}]\' http://0.0.0.0:"+RUNSERVER_PORT+"/f5/snatranslation/"
     os.popen(CURL_command)  
      
   # get information

   tempDict_box = {}

   for _standbyip_ in standby_device_list:
      ip_String = str(_standbyip_)

      if ip_String not in tempDict_box.keys():
        tempDict_box[unicode(ip_String)] = []

      for _filename_ in fileindatabasedir:
         file_String_pattern = "snatranslationlist."+ip_String+".txt"
         search_result = re.search(file_String_pattern,_filename_,re.I)
         if search_result:
           filename_read = USER_DATABASES_DIR+_filename_
           f = open(filename_read,"r")
           string_content = f.readlines()
           f.close()
           stream = BytesIO(string_content[0])
           data_from_databasefile = JSONParser().parse(stream)

           if u'items' in data_from_databasefile:


             for _origin_dict_ in data_from_databasefile[u'items']:
                if u'origins' in _origin_dict_.keys():

                  dict_tray = {}
                  if unicode(_origin_dict_[u'name']) not in dict_tray.keys():
                    dict_tray[unicode(_origin_dict_[u'name'])] = {}
                    dict_tray[unicode(_origin_dict_[u'name'])][u'origins'] = []

                    
                    for _dictitem_ in _origin_dict_[u'origins']:
                       if _dictitem_[u'name'] not in dict_tray[unicode(_origin_dict_[u'name'])][u'origins']:
                         dict_tray[unicode(_origin_dict_[u'name'])][u'origins'].append(_dictitem_[u'name'])

                    dict_tray[unicode(_origin_dict_[u'name'])][u'translation'] = unicode(str(_origin_dict_[u'translation'].split("/")[-1])) 
                    tempDict_box[unicode(ip_String)].append(dict_tray)

   return tempDict_box


@api_view(['GET','POST'])
@csrf_exempt
def f5_snatranslation(request,format=None):

   # get method
   if request.method == 'GET':
      try:
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

         # show get the data
         _contents_in_ = show_snatranslation_filedb(standby_device_list)

      except:
         # read db file
         return Response(_contents_in_)

      # return value 
      return Response(_contents_in_)


   elif request.method == 'POST':

      try:
        _input_ = JSONParser().parse(request)
        if re.match(ENCAP_PASSWORD,str(_input_[0]['auth_key'])):


           # log message
           f = open(LOG_FILE,"a")
           _date_ = os.popen("date").read().strip()
           log_msg = _date_+" from : "+request.META['REMOTE_ADDR']+" , method POST request to run f5_snatranslation!\n"
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

           # memory database creation
           fileindatabasedir = os.listdir(USER_DATABASES_DIR) 

           # send curl command to device
           _threads_ = []
           for _ip_address_ in standby_device_list:
              th = threading.Thread(target=get_snatranslation_info, args=(_ip_address_,))
              th.start()
              _threads_.append(th)
           for th in _threads_:
              th.join()

           # return completed values  
           message = "snatranslation databases are updated!"
           return Response(message)

      except:
        message = "Post method has errors!"
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

