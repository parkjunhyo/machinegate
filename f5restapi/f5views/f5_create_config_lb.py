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


def transfer_crul_to_get_poolmember_info(_DEVICE_IP_):
    
    fileindatabasedir = os.listdir(USER_DATABASES_DIR)
    for _filename_ in fileindatabasedir:
       if re.search("virtualserverlist."+_DEVICE_IP_+".txt",_filename_):
          
          f = open(USER_DATABASES_DIR+_filename_,"r")
          _contents_ = f.readlines()
          f.close()
          stream = BytesIO(_contents_[0])
          data_from_file = JSONParser().parse(stream)

          _temp_list_box_ = []
          for _dict_Data_ in data_from_file["items"]:

             # findout pool information and virtual server information
             if u'pool' in _dict_Data_.keys() or str(u'pool') in _dict_Data_.keys():

                dictionary_tray = {}

                _poolname_ = str(_dict_Data_[u'pool']).strip().split("/")[-1]
                CURL_command = "curl -sk -u "+USER_NAME+":"+USER_PASSWORD+" https://"+_DEVICE_IP_+"/mgmt/tm/ltm/pool/"+_poolname_+" -H 'Content-Type: application/json'"
                get_info = os.popen(CURL_command).read().strip()
                stream = BytesIO(get_info)
                data_from_file = JSONParser().parse(stream)

                dictionary_tray = copy.copy(data_from_file)

                CURL_command = "curl -sk -u "+USER_NAME+":"+USER_PASSWORD+" https://"+_DEVICE_IP_+"/mgmt/tm/ltm/pool/"+_poolname_+"/members/ -H 'Content-Type: application/json'"
                get_info = os.popen(CURL_command).read().strip()
                stream = BytesIO(get_info)
                data_from_file = JSONParser().parse(stream)

                POOLMEMBER_list = []
                POOLMEMBER_status = {}
                for _POOLDATA_ in data_from_file[u'items']:
                    if str(_POOLDATA_[u'fullPath']) not in POOLMEMBER_list:
                       POOLMEMBER_list.append(str(_POOLDATA_[u'fullPath']))
                       POOLMEMBER_status[str(_POOLDATA_[u'fullPath'])] = str(_POOLDATA_[u'state'])

                dictionary_tray['poolmember_names'] = POOLMEMBER_list
                dictionary_tray['poolmember_status'] = POOLMEMBER_status
                _temp_list_box_.append(dictionary_tray)

          # database for pool information create
          _temp_write_ = {}
          _temp_write_['items'] = _temp_list_box_
          f = open(USER_DATABASES_DIR+"poollist."+_DEVICE_IP_+".txt","w")
          f.write(json.dumps(_temp_write_))
          f.close()

    # threading must have
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

                _Re_Poolinfo_ = {}
                for _dict_Data_ in data_from_file[u'items']:
                   ### 2016.05.11 : change pool name to pool name with status information 
                   # _Re_Poolinfo_[str(_dict_Data_[u'name'])] = _dict_Data_[u'poolmember_names']
                   #
                   _Re_Poolinfo_[str(_dict_Data_[u'name'])] = _dict_Data_[u'poolmember_status']

                # Virtual Server Information
                _filename_for_virtualserver_ = USER_DATABASES_DIR+"virtualserverlist."+_database_target_+".txt"
                f = open(_filename_for_virtualserver_,"r")
                _contents_ = f.readlines()
                f.close()
                stream = BytesIO(_contents_[0])
                data_from_file = JSONParser().parse(stream)

                virtualserver_and_pool_info_list = []
                for _dict_Data_ in data_from_file[u'items']:
                   _temp_dict_box_ = {}
                   if u'pool' in _dict_Data_.keys() or str(u'pool') in _dict_Data_.keys():
                      _temp_dict_box_[str(_dict_Data_[u"fullPath"]).strip().split("/")[-1]] = str(_dict_Data_[u"destination"]).strip().split("/")[-1]
                      _temp_dict_box_[str(_dict_Data_[u"pool"]).strip().split("/")[-1]] = _Re_Poolinfo_[str(_dict_Data_[u"pool"]).strip().split("/")[-1]]
                      virtualserver_and_pool_info_list.append(_temp_dict_box_)

                # Virtual Server Information
                virtualserver_and_pool_info_dict[_database_target_] = virtualserver_and_pool_info_list
    except:
       # except
       virtualserver_and_pool_info_dict = {}
       return virtualserver_and_pool_info_dict
    

    # threading must have
    time.sleep(0)
    return virtualserver_and_pool_info_dict


@api_view(['GET','POST'])
@csrf_exempt
def f5_create_config_lb(request,format=None):

   # get method
   if request.method == 'GET':

      # get the result data and return
      message = get_poolinfo()
      return Response(message)


   elif request.method == 'POST':

      try:

        _input_ = JSONParser().parse(request)
        
        if re.match(ENCAP_PASSWORD,str(_input_[0]['auth_key'])):

           # virtual server ip and port validation check
           _keyname_count_ = {}
           for _dictData_ in _input_[0][u'items']:
              _keyname_string_ = str(_dictData_[u'virtual_ip_port'])
              if _keyname_string_ not in _keyname_count_.keys():
                 _keyname_count_[_keyname_string_] = int(1)
              else:
                 _keyname_count_[_keyname_string_] = _keyname_count_[_keyname_string_] + 1

           _valid_dictData_list_ = []
           for _dictData_ in _input_[0][u'items']:
              _keyname_string_ = str(_dictData_[u'virtual_ip_port'])
              if int(_keyname_count_[_keyname_string_]) == int(1):
                 _valid_dictData_list_.append(_dictData_)

           _valid_virtual_ip_port_dictData_list_ = copy.copy(_valid_dictData_list_)

           # host name duplication check according to device
           _valid_dictData_ = {}
           for _dictData_ in _valid_virtual_ip_port_dictData_list_:
              _device_name_ = str(_dictData_[u'device'])
              if _device_name_ not in _valid_dictData_.keys():
                 _valid_dictData_[_device_name_] = {}                  


           for _dictData_ in _valid_virtual_ip_port_dictData_list_:
              _device_name_ = str(_dictData_[u'device'])
              _server_name_ = str(_dictData_[u'servername'])
              if _server_name_ not in _valid_dictData_[_device_name_].keys():
                 _valid_dictData_[_device_name_][_server_name_] = int(1)
              else:
                 _valid_dictData_[_device_name_][_server_name_] = _valid_dictData_[_device_name_][_server_name_] + 1

           _valid_dictData_list_ = []              
           for _dictData_ in _valid_virtual_ip_port_dictData_list_:
              _device_name_ = str(_dictData_[u'device'])
              _server_name_ = str(_dictData_[u'servername'])
              if int(_valid_dictData_[_device_name_][_server_name_]) == int(1):
                 _valid_dictData_list_.append(_dictData_)

           _valid_input_dictData_list_ = copy.copy(_valid_dictData_list_)

           print _valid_input_dictData_list_
           

           #[{u'device': u'KRIS10-PUBS01-5000L4', u'poolmembers': [u'172.22.192.51:80', u'172.22.192.52:80', u'172.22.192.53:80'], u'hostname': u'testhost', u'virtual_ip_port': u'172.22.198.48:443'}, {u'device': u'KRIS10-PUBS01-5000L4', u'poolmembers': [u'172.22.192.51:80', u'172.22.192.52:80', u'172.22.192.53:80'], u'hostname': u'testhost', u'virtual_ip_port': u'172.22.198.48:443'}]

           # log message
           #f = open(LOG_FILE,"a")
           #_date_ = os.popen("date").read().strip()
           #log_msg = _date_+" from : "+request.META['REMOTE_ADDR']+" , method POST request to run f5_poolmemberlist function!\n"
           #f.write(log_msg)
           #f.close()

           # read db file
           #_devicelist_db_ = USER_DATABASES_DIR + "devicelist.txt"
           #f = open(_devicelist_db_,'r')
           #_string_contents_ = f.readlines()
           #f.close()
           #stream = BytesIO(_string_contents_[0])
           #_data_from_devicelist_db_= JSONParser().parse(stream)

           # standby server list
           #standby_device_list = []           
           #for _dict_information_ in _data_from_devicelist_db_:
           #   if re.match('standby',str(_dict_information_[u'failover'])):
           #      if str(_dict_information_[u'ip']) not in standby_device_list:
           #         standby_device_list.append(str(_dict_information_[u'ip']))

           # delete all databasefile
           #fileindatabasedir = os.listdir(USER_DATABASES_DIR)
           #for _filename_ in fileindatabasedir:
           #    if re.search("poollist.[0-9]+.[0-9]+.[0-9]+.[0-9]+.txt",_filename_) or re.search("virtualserverlist.[0-9]+.[0-9]+.[0-9]+.[0-9]+.txt",_filename_):
           #       os.popen("rm -rf "+USER_DATABASES_DIR+_filename_)

           # send curl command to device for virtual serverlist update
           #_threads_ = []
           #for _ip_address_ in standby_device_list:
           #   th = threading.Thread(target=transfer_crul_to_get_virtualserver_info, args=(_ip_address_,))
           #   th.start()
           #   _threads_.append(th)
           #for th in _threads_:
           #   th.join()
           
           # get pool member information from the database file
           #_threads_ = []
           #for _ip_address_ in standby_device_list:
           #   th = threading.Thread(target=transfer_crul_to_get_poolmember_info, args=(_ip_address_,))
           #   th.start()
           #   _threads_.append(th)
           #for th in _threads_:
           #   th.join()

           # get the result data and return
           #message = get_poolinfo()
           message = [{}]
           return Response(message)


      except:
        message = [{}]
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

