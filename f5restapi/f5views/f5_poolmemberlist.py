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

#def transfer_crul_to_get_virtualserver_info(_DEVICE_IP_):
#
#    # clean up database file
#    database_filename = USER_DATABASES_DIR+"virtualserverlist."+_DEVICE_IP_+".txt"
#    f = open(database_filename,"w")
#    f.close()
#
#    # send curl message
#    CURL_command = "curl -sk -u "+USER_NAME+":"+USER_PASSWORD+" https://"+_DEVICE_IP_+"/mgmt/tm/ltm/virtual/ -H 'Content-Type: application/json'"
#    get_info = os.popen(CURL_command).read().strip()
#    f = open(database_filename,"w")
#    f.write(get_info)
#    f.close()
#    
#    # threading must have
#    time.sleep(0)



def transfer_crul_to_get_poolmember_info(_DEVICE_IP_):

    CURL_command = "curl -sk -u "+USER_NAME+":"+USER_PASSWORD+" https://"+_DEVICE_IP_+"/mgmt/tm/ltm/pool/ -H 'Content-Type: application/json'"
    get_info = os.popen(CURL_command).read().strip()
    stream = BytesIO(get_info)
    data_from_CURL_command = JSONParser().parse(stream)

    all_data_poollist_from_command = copy.copy(data_from_CURL_command)


    all_data_poollist_recreated = []
    for _dictdata_poollist_ in all_data_poollist_from_command[u'items']:

       _poolname_ = str(_dictdata_poollist_[u'name'])
       # find virtual server
       fileindatabasedir = os.listdir(USER_DATABASES_DIR)
       for _filename_ in fileindatabasedir:

          if re.search("virtualserverlist."+_DEVICE_IP_+".txt",_filename_):
            f = open(USER_DATABASES_DIR+_filename_,"r")
            _contents_ = f.readlines()
            stream = BytesIO(_contents_[0])
            data_from_file = JSONParser().parse(stream)

            virtual_servername_list = []
            for _loop1_ in data_from_file[u'items']:
                if u'pool' in _loop1_.keys() or str(u'pool') in _loop1_.keys():
                  if re.search(_poolname_,_loop1_[u'pool']):
                    if str(_loop1_[u'name']) not in virtual_servername_list:
                      virtual_servername_list.append(str(_loop1_[u'name']))
            continue      
       # find virtual server
       _virtualserver_names_list_ = copy.copy(virtual_servername_list)

       # get pool information
       CURL_command = "curl -sk -u "+USER_NAME+":"+USER_PASSWORD+" https://"+_DEVICE_IP_+"/mgmt/tm/ltm/pool/"+_poolname_+" -H 'Content-Type: application/json'"
       get_info = os.popen(CURL_command).read().strip()
       stream = BytesIO(get_info)
       data_from_CURL_command = JSONParser().parse(stream)
       spec_data_pool_from_command = copy.copy(data_from_CURL_command)
       
       CURL_command = "curl -sk -u "+USER_NAME+":"+USER_PASSWORD+" https://"+_DEVICE_IP_+"/mgmt/tm/ltm/pool/"+_poolname_+"/members/ -H 'Content-Type: application/json'" 
       get_info = os.popen(CURL_command).read().strip()
       stream = BytesIO(get_info)
       data_from_CURL_command = JSONParser().parse(stream)
       spec_data_poolmember_from_command = copy.copy(data_from_CURL_command)

       members_status_dict = {}
       for _loop1_ in spec_data_poolmember_from_command[u'items']:
          members_status_dict[str(_loop1_[u'fullPath'])] = str(_loop1_[u'state'])

       spec_data_pool_from_command[u'virtualserver_names_list'] = _virtualserver_names_list_
       spec_data_pool_from_command[u'poolmembers_status_list'] = members_status_dict

       all_data_poollist_recreated.append(spec_data_pool_from_command)

    # create db file
    _temp_write_ = {}
    _temp_write_['items'] = all_data_poollist_recreated
    f = open(USER_DATABASES_DIR+"poollist."+_DEVICE_IP_+".txt","w")
    f.write(json.dumps(_temp_write_))
    f.close()
    
    # thread timeout 
    time.sleep(0)
  
def get_poolinfo():

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

       fileindatabasedir = os.listdir(USER_DATABASES_DIR)
       # re-arrange the pool information
       virtualserver_and_pool_info_dict = {}
       for _filename_ in fileindatabasedir:
          if re.search("poollist.[0-9]+.[0-9]+.[0-9]+.[0-9]+.txt",_filename_):

             _database_target_ = re.search("[0-9]+.[0-9]+.[0-9]+.[0-9]+",_filename_).group(0)
             if str(_database_target_).strip() in standby_device_list:

                # Pool information Re-arrange.
                f = open(USER_DATABASES_DIR+_filename_,"r")
                _contents_ = f.readlines()
                f.close()
                stream = BytesIO(_contents_[0])
                data_from_file = JSONParser().parse(stream)
                virtualserver_and_pool_info_dict[str(_database_target_)] = {}
                for _dict_Data_ in data_from_file[u'items']:
                   virtualserver_and_pool_info_dict[str(_database_target_)][str(_dict_Data_[u'name'])] = {}
                   virtualserver_and_pool_info_dict[str(_database_target_)][str(_dict_Data_[u'name'])][u'virtualserver_names'] = _dict_Data_[u'virtualserver_names_list']
                   virtualserver_and_pool_info_dict[str(_database_target_)][str(_dict_Data_[u'name'])][u'poolmembers_status'] = _dict_Data_[u'poolmembers_status_list']
                   monitors_list = []
                   if u'monitor' in _dict_Data_.keys():
                     monitors_list = str(_dict_Data_[u'monitor']).split(" and ")
                   virtualserver_and_pool_info_dict[str(_database_target_)][str(_dict_Data_[u'name'])][u'monitors'] = monitors_list 

    except:
       # except
       virtualserver_and_pool_info_dict = {}
       return virtualserver_and_pool_info_dict
    

    # threading must have
    time.sleep(0)
    return virtualserver_and_pool_info_dict


@api_view(['GET','POST'])
@csrf_exempt
def f5_poolmemberlist(request,format=None):

   # get method
   if request.method == 'GET':

      # get the result data and return
      message = get_poolinfo()
      return Response(message)


   elif request.method == 'POST':

      try:
        _input_ = JSONParser().parse(request)
        if re.match(ENCAP_PASSWORD,str(_input_[0]['auth_key'])):

           # log message
           f = open(LOG_FILE,"a")
           _date_ = os.popen("date").read().strip()
           log_msg = _date_+" from : "+request.META['REMOTE_ADDR']+" , method POST request to run f5_poolmemberlist function!\n"
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

           # delete all databasefile
           fileindatabasedir = os.listdir(USER_DATABASES_DIR)
           for _filename_ in fileindatabasedir:
               if re.search("poollist.[0-9]+.[0-9]+.[0-9]+.[0-9]+.txt",_filename_) or re.search("virtualserverlist.[0-9]+.[0-9]+.[0-9]+.[0-9]+.txt",_filename_):
                  get_info = os.popen("rm -rf "+USER_DATABASES_DIR+_filename_)

           # send curl command to device for virtual serverlist update
           CURL_command = "curl -H \"Accept: application/json\" -X POST -d \'[{\"auth_key\":\""+ENCAP_PASSWORD+"\"}]\' http://0.0.0.0:"+RUNSERVER_PORT+"/f5/virtualserverlist/"
           get_info = os.popen(CURL_command).read().strip()

           #_threads_ = []
           #for _ip_address_ in standby_device_list:
           #   th = threading.Thread(target=transfer_crul_to_get_virtualserver_info, args=(_ip_address_,))
           #   th.start()
           #   _threads_.append(th)
           #for th in _threads_:
           #   th.join()
           
           # get pool member information from the database file
           _threads_ = []
           for _ip_address_ in standby_device_list:
              th = threading.Thread(target=transfer_crul_to_get_poolmember_info, args=(_ip_address_,))
              th.start()
              _threads_.append(th)
           for th in _threads_:
              th.join()

           # get the result data and return
           message = get_poolinfo()
           return Response(message)


      except:
        message = [{}]
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

