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
from f5restapi.setting import RUNSERVER_PORT

class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders its content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)

  
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

           # read device list file
           _devicelist_db_ = USER_DATABASES_DIR + "devicelist.txt"
           f = open(_devicelist_db_,'r')
           _string_contents_ = f.readlines()
           f.close()
           stream = BytesIO(_string_contents_[0])
           _data_from_devicelist_db_= JSONParser().parse(stream)

           _devicelist_file_db_cache_ = copy.copy(_data_from_devicelist_db_)

           # CHANGE THE DEVICE NAME TO IP ADDRESS
           _user_input_ = copy.copy(_input_[0][u'items'])
           _device_converted_to_ip_user_input_ = []
           for _loop_1_ in _user_input_:
              _device_name_ = str(_loop_1_[u'device'])
              for _loop_2_ in _data_from_devicelist_db_:
                  _clustername_ = str(_loop_2_[u'clustername'])
                  _devicehostname_ = str(_loop_2_[u'devicehostname'])
                  _device_failover_ = str(_loop_2_[u'failover'])
                  if (re.search(_device_name_,_clustername_) or re.search(_device_name_,_devicehostname_)) and re.search(_device_failover_,'active'):
                     _loop_1_[u'device'] = str(_loop_2_[u'ip'])
                     _device_converted_to_ip_user_input_.append(_loop_1_)

           # CONFIRM THE INPUT VIRTUAL IP AND PORT UNIQUE
           _temp_box_ = {}
           for _loop_1_ in _device_converted_to_ip_user_input_:
              _keyname_ = str(_loop_1_[u'device'])
              if _keyname_ not in _temp_box_.keys():
                 _temp_box_[_keyname_] = {}

           for _loop_1_ in _device_converted_to_ip_user_input_:
              _keyname_ = str(_loop_1_[u'device'])
              _virtualipport_ = str(_loop_1_[u'virtual_ip_port'])
              if _virtualipport_ not in _temp_box_[_keyname_].keys():
                 _temp_box_[_keyname_][_virtualipport_] = int(1)
              else:
                 _temp_box_[_keyname_][_virtualipport_] = _temp_box_[_keyname_][_virtualipport_] + int(1)

           _virtualipport_unique_user_input_ = []
           for _loop_1_ in _device_converted_to_ip_user_input_:
              _keyname_ = str(_loop_1_[u'device'])
              _virtualipport_ = str(_loop_1_[u'virtual_ip_port'])
              if int(_temp_box_[_keyname_][_virtualipport_]) == int(1):
                 _virtualipport_unique_user_input_.append(_loop_1_)

           # CONFIRM THE INPUT SERVER NAME IS UNIQUE
           _temp_box_ = {}
           for _loop_1_ in _virtualipport_unique_user_input_:
              _keyname_ = str(_loop_1_[u'device'])
              if _keyname_ not in _temp_box_.keys():
                 _temp_box_[_keyname_] = {}
 
           for _loop_1_ in _virtualipport_unique_user_input_:
              _keyname_ = str(_loop_1_[u'device'])
              _servername_ = str(_loop_1_[u'servername']) 
              if _servername_ not in _temp_box_[_keyname_].keys():
                _temp_box_[_keyname_][_servername_] = int(1)
              else:
                _temp_box_[_keyname_][_servername_] = _temp_box_[_keyname_][_servername_] + int(1)

           _servername_unique_user_input_ = []
           for _loop_1_ in _virtualipport_unique_user_input_:
              _keyname_ = str(_loop_1_[u'device'])
              _servername_ = str(_loop_1_[u'servername'])
              if int(_temp_box_[_keyname_][_servername_]) == int(1):
                 _servername_unique_user_input_.append(_loop_1_)

           # CREATE THE POOL AND VIRTUAL NAME

# {u'haclustername': u'KRIS10-SRPS02-2000L4.com', u'clustername': u'KRIS10-SRPS01-2000L4.com', u'ip': u'10.10.77.45', u'failover': u'active', u'devicehostname': u'KRIS10-SRPS01-2000L4.com', u'devicegroupname': u'dg'}

           # [{u'device': u'KRIS10-PUBS01-5000L4', u'poolmembers': [u'172.22.192.51:80', u'172.22.192.52:80', u'172.22.192.53:80'], u'servername': u'testhost', u'virtual_ip_port': u'172.22.198.48:443'}, {u'device': u'KRIS10-DMZS01-5000L4', u'poolmembers': [u'172.22.192.51:80', u'172.22.192.52:80', u'172.22.192.53:80'], u'servername': u'testhost', u'virtual_ip_port': u'172.22.198.47:443'}]


           _added_createname_user_input_ = []
           for _loop_1_ in _servername_unique_user_input_:
              # FIND SERVER PORT and create pool name
              _serverport_list_ = []
              for _loop_2_ in _loop_1_[u'poolmembers']:
                 _server_port_ = str(str(_loop_2_).strip().split(':')[-1])
                 if _server_port_ not in _serverport_list_:
                   _serverport_list_.append(_server_port_)
              _created_pool_name_ = str('p_')+str(_loop_1_[u'servername'])+str('_')+str('_'.join(_serverport_list_))
              _virtualip_ = str(str(_loop_1_[u'virtual_ip_port']).strip().split(':')[0])
              _virtualip_name_ = str('.'.join(_virtualip_.strip().split('.')[2:]))
              _virtualport_ = str(str(_loop_1_[u'virtual_ip_port']).strip().split(':')[1])
              _created_virtualserver_name_ = str('v_')+_virtualip_name_+str('_')+str(_loop_1_[u'servername'])+str('_')+_virtualport_
              # add information into the dict
              _loop_1_[u'created_poolname'] = str(_created_pool_name_)
              _loop_1_[u'created_virtualservername'] = str(_created_virtualserver_name_)
              _added_createname_user_input_.append(_loop_1_)
             

           # UPDATE DATABASE FILE
           CURL_command = "curl -H \"Accept: application/json\" -X POST -d \'[{\"auth_key\":\""+ENCAP_PASSWORD+"\"}]\' http://0.0.0.0:"+RUNSERVER_PORT+"/f5/poolmemberlist/"

           # FIND OUT NODE Validation
           _nodestatus_confirmed_user_input_ = []
           for _dict_Data_ in _added_createname_user_input_:

              _target_deviceip_ = str(_dict_Data_[u'device'])
              for _loop1_ in _devicelist_file_db_cache_:
                 if re.search(str(_loop1_[u'ip']),_target_deviceip_):
                    _backup_devicename_ = str(_loop1_[u'haclustername'])
                    break
              for _loop1_ in _devicelist_file_db_cache_:
                 if re.search(str(_loop1_[u'clustername']),_backup_devicename_):
                    _backup_deviceip_ = str(_loop1_[u'ip'])

              #CURL_command = "curl -sk -u "+USER_NAME+":"+USER_PASSWORD+" https://"+str(_backup_deviceip_)+"/mgmt/tm/ltm/pool/ -H 'Content-Type: application/json'"
              #print CURL_command
              #get_info = os.popen(CURL_command).read().strip()
              #stream = BytesIO(get_info)
              #data_from_file = JSONParser().parse(stream)
   
              #print data_from_file
              _matched_poollist_dbfile_name_ = USER_DATABASES_DIR + 'poollist.'+str(_backup_deviceip_)+'.txt'
              f = open(_matched_poollist_dbfile_name_,'r')
              _string_contents_ = f.readlines()
              f.close()
              stream = BytesIO(_string_contents_[0])
              _data_from_file_ = JSONParser().parse(stream)

              _temp_dict_bay_ = {}
              for _loop1_ in _data_from_file_[u'items']:
                 _temp_dict_bay_[str(_loop1_[u'name'])] = []
                 for _loop2_ in _loop1_[u'poolmember_names']:
                    if str(_loop2_) not in _temp_dict_bay_[str(_loop1_[u'name'])]:
                      _temp_dict_bay_[str(_loop1_[u'name'])].append(str(_loop2_))

              print _temp_dict_bay_.keys()
              print len(_temp_dict_bay_.keys())

              _counting_bay_ = {}
              for _loop1_ in _dict_Data_[u'poolmembers']:
                 for _loop2_ in _temp_dict_bay_.keys():
                    for _loop3_ in _temp_dict_bay_[_loop2_]:
                        if re.search(str(_loop1_),str(_loop3_)):
                           if str(_loop2_) not in _counting_bay_.keys():
                              _counting_bay_[str(_loop2_)] = int(1)
                           else:
                              _counting_bay_[str(_loop2_)] = _counting_bay_[str(_loop2_)] + int(1)

              valid_poolname_list = []
              for _loop1_ in _counting_bay_.keys():
                 if (len(_dict_Data_[u'poolmembers']) == int(_counting_bay_[_loop1_])) and (len(_dict_Data_[u'poolmembers']) == len(_temp_dict_bay_[_loop1_])):
                    if str(_loop1_) not in valid_poolname_list:
                       valid_poolname_list.append(str(_loop1_))

              if len(valid_poolname_list) != 0:
                valid_poolname_list.sort()
                _dict_Data_[u'created_poolname'] = str(valid_poolname_list[0])
                _dict_Data_[u'poolname_matchstatus'] = 'matched'
              else:
                _dict_Data_[u'poolname_matchstatus'] = 'none'
              _nodestatus_confirmed_user_input_.append(_dict_Data_) 


           # FIND OUT DUPLICATION WITH DATABASE FILE
           print _added_createname_user_input_
           print "#####"
           print _nodestatus_confirmed_user_input_

           print "----"

           fileindatabasedir = os.listdir(USER_DATABASES_DIR)
           for _filename_ in fileindatabasedir:
              if re.search("virtualserverlist.[0-9]+.[0-9]+.[0-9]+.[0-9]+.txt",_filename_):
                 _filename_ = USER_DATABASES_DIR + _filename_
                 f = open(_filename_,'r')
                 _string_contents_ = f.readlines()
                 f.close()
                 stream = BytesIO(_string_contents_[0])
                 _data_from_file_ = JSONParser().parse(stream)
                 print _filename_
              if re.search("poollist.[0-9]+.[0-9]+.[0-9]+.[0-9]+.txt",_filename_):
                 _filename_ = USER_DATABASES_DIR + _filename_
                 print _filename_





           #_devicename_clustername_ = {}
           #_devicename_haclustername_ = {}
           #_clustername_ip_ = {}
           #for _dictData_ in _data_from_devicelist_db_:
           #   _devicename_clustername_[str(_dictData_[u'devicehostname'])] = str(_dictData_[u'clustername'])
           #   _devicename_haclustername_[str(_dictData_[u'devicehostname'])] = str(_dictData_[u'haclustername'])
           #   _clustername_ip_[str(_dictData_[u'clustername'])] = str(_dictData_[u'ip'])

           #print _devicename_clustername_
           #print _devicename_haclustername_
           #print _clustername_ip_




           #print _data_from_devicelist_db_
           #u'device': u'KRIS10-PUBS01-5000L4'           

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

