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
from f5restapi.setting import THREAD_TIMEOUT


class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders its content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)


def get_virtualserver_profile_info(_database_target_,profile_client_ssl_info,file_ssl_cert_info,file_ssl_key_info):

   fileindatabasedir = os.listdir(USER_DATABASES_DIR)

   combination_result = {}
   for _filename_ in fileindatabasedir:
      search_result = re.search("virtualserverlist."+str(_database_target_)+".txt",_filename_)
      if search_result:

        if unicode(str(_database_target_)) not in combination_result.keys():

          combination_result[unicode(str(_database_target_))] = {}
          filename_read = USER_DATABASES_DIR+_filename_
          f = open(filename_read,"r")
          string_content = f.readlines()
          f.close()
          stream = BytesIO(string_content[0])
          data_from_databasefile = JSONParser().parse(stream)
 
          for _dataDict_value_ in data_from_databasefile[u'items']:
             CURL_command = "curl -sk -u "+USER_NAME+":"+USER_PASSWORD+" https://"+str(_database_target_)+"/mgmt/tm/ltm/virtual/"+str(_dataDict_value_[u'name'])+"/profiles/ -H 'Content-Type: application/json'"
             string_content = os.popen(CURL_command).read().strip()
             stream = BytesIO(string_content)
             data_from_file = JSONParser().parse(stream)

             if u'items' in data_from_file.keys():
               for _innerDict_values_ in data_from_file[u'items']:
                  if unicode("context") in _innerDict_values_.keys():

                    if re.search("clientside",str(_innerDict_values_[u'context'])):
                      string_fullPath = str(_innerDict_values_[u'fullPath']).strip().split("/")[-1]
                      if unicode(string_fullPath) not in combination_result[unicode(str(_database_target_))].keys():
                        combination_result[unicode(str(_database_target_))][unicode(string_fullPath)] = {}
                        combination_result[unicode(str(_database_target_))][unicode(string_fullPath)][unicode("virtualservers")] = []
                        combination_result[unicode(str(_database_target_))][unicode(string_fullPath)][unicode("certKeyChain")] = {}

                      if unicode(_dataDict_value_[u'name']) not in combination_result[unicode(str(_database_target_))][unicode(string_fullPath)][unicode("virtualservers")]:
                        combination_result[unicode(str(_database_target_))][unicode(string_fullPath)][unicode("virtualservers")].append(unicode(_dataDict_value_[u'name']))

                      # find out the 
                      if len(combination_result[unicode(str(_database_target_))][unicode(string_fullPath)][unicode("certKeyChain")].keys()) == 0:
                        matched_profile_clientsslinfo = profile_client_ssl_info[unicode(str(_database_target_))][unicode(string_fullPath)][unicode("certKeyChain")]
                        _innerBox_tempDict_ = {}
                        for _innerLoop1_Dict_ in matched_profile_clientsslinfo.keys():
                           if _innerLoop1_Dict_ not in _innerBox_tempDict_.keys():
                             _innerBox_tempDict_[_innerLoop1_Dict_] = {}
                             for _innerLoop2_Dict_ in matched_profile_clientsslinfo[_innerLoop1_Dict_]:
                                if _innerLoop2_Dict_ not in _innerBox_tempDict_[_innerLoop1_Dict_].keys():
                                  _innerBox_tempDict_[_innerLoop1_Dict_][_innerLoop2_Dict_] = {}
                                  name_string_value = str(matched_profile_clientsslinfo[_innerLoop1_Dict_][_innerLoop2_Dict_])
                                  name_string = str(name_string_value.strip().split("/")[-1])
                                  _innerBox_tempDict_[_innerLoop1_Dict_][_innerLoop2_Dict_][unicode("name")] = unicode(name_string)

                                  if re.search(".crt",name_string_value,re.I):
                                    _innerBox_tempDict_[_innerLoop1_Dict_][_innerLoop2_Dict_][u'expirationString'] = file_ssl_cert_info[unicode(str(_database_target_))][unicode(name_string)][u'expirationString']
                                    _innerBox_tempDict_[_innerLoop1_Dict_][_innerLoop2_Dict_][u'expirationDate'] = file_ssl_cert_info[unicode(str(_database_target_))][unicode(name_string)][u'expirationDate']
                                    _innerBox_tempDict_[_innerLoop1_Dict_][_innerLoop2_Dict_][u'lastUpdateTime'] = file_ssl_cert_info[unicode(str(_database_target_))][unicode(name_string)][u'lastUpdateTime']
                                    _innerBox_tempDict_[_innerLoop1_Dict_][_innerLoop2_Dict_][u'createTime'] = file_ssl_cert_info[unicode(str(_database_target_))][unicode(name_string)][u'createTime']
                                    _innerBox_tempDict_[_innerLoop1_Dict_][_innerLoop2_Dict_][u'keyType'] = file_ssl_cert_info[unicode(str(_database_target_))][unicode(name_string)][u'keyType']
                                  if re.search(".key",name_string_value,re.I):
                                    _innerBox_tempDict_[_innerLoop1_Dict_][_innerLoop2_Dict_][u'lastUpdateTime'] = file_ssl_key_info[unicode(str(_database_target_))][unicode(name_string)][u'lastUpdateTime']
                                    _innerBox_tempDict_[_innerLoop1_Dict_][_innerLoop2_Dict_][u'createTime'] = file_ssl_key_info[unicode(str(_database_target_))][unicode(name_string)][u'createTime']
                                    _innerBox_tempDict_[_innerLoop1_Dict_][_innerLoop2_Dict_][u'keyType'] = file_ssl_key_info[unicode(str(_database_target_))][unicode(name_string)][u'keyType']

                        combination_result[unicode(str(_database_target_))][unicode(string_fullPath)][unicode("certKeyChain")] = _innerBox_tempDict_
    
   # file write
   filename_description = "profile.clientside."+str(_database_target_)+".txt"
   filename_writing = USER_DATABASES_DIR+filename_description
   for _filename_ in fileindatabasedir:
      search_result = re.search(filename_description,_filename_)
      if search_result:
        delete_cmd = "rm -rf "+filename_writing
        os.popen(delete_cmd)
   f = open(filename_writing,"w")
   writing_string = json.dumps(combination_result)
   f.write(writing_string)
   f.close()
        
   # threading must have
   time.sleep(0)

def show_profile_clientside_filedb(standby_device_list):
   fileindatabasedir = os.listdir(USER_DATABASES_DIR) 

   _temp_Listbox_ = []   
   for _standbyip_ in standby_device_list:
      ip_String = str(_standbyip_)
      for _filename_ in fileindatabasedir:
         file_String_pattern = "profile.clientside."+ip_String+".txt"
         search_result = re.search(file_String_pattern,_filename_,re.I)
         if search_result:
           filename_read = USER_DATABASES_DIR+_filename_
           f = open(filename_read,"r")
           string_content = f.readlines()
           f.close()
           stream = BytesIO(string_content[0])
           data_from_databasefile = JSONParser().parse(stream)
           # add data
           _temp_Listbox_.append(data_from_databasefile)

   return _temp_Listbox_


@api_view(['GET','POST'])
@csrf_exempt
def f5_virtualserverlist_profile_clientside(request,format=None):

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

         _contents_in_ = show_profile_clientside_filedb(standby_device_list)

      except:
         # read db file
         _contents_in_ = "GET method has errors!"
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
           log_msg = _date_+" from : "+request.META['REMOTE_ADDR']+" , method POST request to run f5_virtualserverlist_profile_clientside!\n"
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

           # 
           file_ssl_key_info = {}
           for _filename_ in fileindatabasedir:
              search_result = re.search("file.ssl_key.([0-9]+.[0-9]+.[0-9]+.[0-9]+).txt",_filename_)
              if search_result:
                search_ip = search_result.group(1)
                if unicode(search_ip) not in file_ssl_key_info.keys():
                  file_ssl_key_info[unicode(search_ip)] = {}
                  filename_read = USER_DATABASES_DIR+_filename_
                  f = open(filename_read,"r")
                  string_content = f.readlines()
                  f.close()
                  stream = BytesIO(string_content[0])
                  data_from_databasefile = JSONParser().parse(stream)
                  for _dataDict_value_ in data_from_databasefile[u'items']:
                     if unicode(_dataDict_value_[u'name']) not in file_ssl_key_info[unicode(search_ip)].keys():
                       file_ssl_key_info[unicode(search_ip)][unicode(_dataDict_value_[u'name'])] = {}
                       file_ssl_key_info[unicode(search_ip)][unicode(_dataDict_value_[u'name'])][u'lastUpdateTime'] = _dataDict_value_[u'lastUpdateTime']
                       file_ssl_key_info[unicode(search_ip)][unicode(_dataDict_value_[u'name'])][u'createTime'] = _dataDict_value_[u'createTime']
                       file_ssl_key_info[unicode(search_ip)][unicode(_dataDict_value_[u'name'])][u'keyType'] = _dataDict_value_[u'keyType']
           # 
           file_ssl_cert_info = {}
           for _filename_ in fileindatabasedir:
              search_result = re.search("file.ssl_cert.([0-9]+.[0-9]+.[0-9]+.[0-9]+).txt",_filename_)
              if search_result:
                search_ip = search_result.group(1)
                if unicode(search_ip) not in file_ssl_cert_info.keys():
                  file_ssl_cert_info[unicode(search_ip)] = {}
                  filename_read = USER_DATABASES_DIR+_filename_
                  f = open(filename_read,"r")
                  string_content = f.readlines()
                  f.close()
                  stream = BytesIO(string_content[0])
                  data_from_databasefile = JSONParser().parse(stream)
                  for _dataDict_value_ in data_from_databasefile[u'items']:
                     if unicode(_dataDict_value_[u'name']) not in file_ssl_cert_info[unicode(search_ip)].keys():
                       file_ssl_cert_info[unicode(search_ip)][_dataDict_value_[u'name']] = {}
                       file_ssl_cert_info[unicode(search_ip)][_dataDict_value_[u'name']][u'expirationString'] = _dataDict_value_[u'expirationString']
                       file_ssl_cert_info[unicode(search_ip)][_dataDict_value_[u'name']][u'expirationDate'] = _dataDict_value_[u'expirationDate']
                       file_ssl_cert_info[unicode(search_ip)][_dataDict_value_[u'name']][u'lastUpdateTime'] = _dataDict_value_[u'lastUpdateTime']
                       file_ssl_cert_info[unicode(search_ip)][_dataDict_value_[u'name']][u'createTime'] = _dataDict_value_[u'createTime']
                       file_ssl_cert_info[unicode(search_ip)][_dataDict_value_[u'name']][u'keyType'] = _dataDict_value_[u'keyType']
           # 
           profile_client_ssl_info = {}
           for _filename_ in fileindatabasedir:
              search_result = re.search("profile.client_ssl.([0-9]+.[0-9]+.[0-9]+.[0-9]+).txt",_filename_)
              if search_result:
                search_ip = search_result.group(1)
                if unicode(search_ip) not in profile_client_ssl_info.keys():
                  profile_client_ssl_info[unicode(search_ip)] = {}
                  filename_read = USER_DATABASES_DIR+_filename_
                  f = open(filename_read,"r")
                  string_content = f.readlines()
                  f.close()
                  stream = BytesIO(string_content[0])
                  data_from_databasefile = JSONParser().parse(stream)
                  for _dataDict_value_ in data_from_databasefile[u'items']:
                     if unicode(_dataDict_value_[u'name']) not in profile_client_ssl_info[unicode(search_ip)].keys():
                       profile_client_ssl_info[unicode(search_ip)][unicode(_dataDict_value_[u'name'])] = {}
                       profile_client_ssl_info[unicode(search_ip)][unicode(_dataDict_value_[u'name'])][u'certKeyChain'] = {}
                       for _innerDict_ in _dataDict_value_[u'certKeyChain']:
                          if unicode(_innerDict_[u'name']) not in profile_client_ssl_info[unicode(search_ip)][unicode(_dataDict_value_[u'name'])][u'certKeyChain'].keys():
                            profile_client_ssl_info[unicode(search_ip)][unicode(_dataDict_value_[u'name'])][u'certKeyChain'][unicode(_innerDict_[u'name'])] = {}
                            if unicode("cert") in _innerDict_.keys():
                              profile_client_ssl_info[unicode(search_ip)][unicode(_dataDict_value_[u'name'])][u'certKeyChain'][unicode(_innerDict_[u'name'])][unicode("cert")] = _innerDict_[u'cert']
                            if unicode("chain") in _innerDict_.keys():
                              profile_client_ssl_info[unicode(search_ip)][unicode(_dataDict_value_[u'name'])][u'certKeyChain'][unicode(_innerDict_[u'name'])][unicode("chain")] = _innerDict_[u'chain']
                            if unicode("key") in _innerDict_.keys():
                              profile_client_ssl_info[unicode(search_ip)][unicode(_dataDict_value_[u'name'])][u'certKeyChain'][unicode(_innerDict_[u'name'])][unicode("key")] = _innerDict_[u'key']

           # 
           # send curl command to device
           _threads_ = []
           for _ip_address_ in standby_device_list:
              th = threading.Thread(target=get_virtualserver_profile_info, args=(_ip_address_,profile_client_ssl_info,file_ssl_cert_info,file_ssl_key_info,))
              th.start()
              _threads_.append(th)
           for th in _threads_:
              th.join()
           # 
           message = show_profile_clientside_filedb(standby_device_list)

           # return completed values  
           return Response(message)

      except:
        message = "Post method has errors!"
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

