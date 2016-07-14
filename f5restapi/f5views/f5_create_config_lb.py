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


## Curl Command Format
## This is the Global Setting Configuration
## 

## this value is used to create the virtual server name
VIRTUALIP_SPLITE_COUNT = 2

DEFAULT_SETTING = [
                    { 
                      "device":["10.10.77.29","10.10.77.30","10.10.77.45","10.10.77.46"],
                      "sticky":"{\"name\":\"source_addr_300\"}",
                      "profiles":"\"fastL4\""
                    },
                    {
                      "device":["10.10.30.101","10.10.30.102"],
                      "sticky":"{\"name\":\"source_addr_300\"}",
                      "profiles":"\"fastL4_loose\""
                    },
                    {
                      "device":["10.10.77.31","10.10.77.32","10.10.77.33","10.10.77.34"],
                      "sticky":"",
                      "profiles":"\"fastL4\""
                    }
                  ]


#### command formatting
# virtual
F5_LTM_VIRTUAL = "curl -sk -u %(username)s:%(password)s https://%(device)s/mgmt/tm/ltm/virtual/"
F5_LTM_VIRTUAL_CURL_URL = F5_LTM_VIRTUAL + " -H 'Content-Type: application/json'"
F5_LTM_VIRTUAL_POST_CURL_URL = F5_LTM_VIRTUAL_CURL_URL + " -X POST -d "

# pool
F5_LTM_POOL = "curl -sk -u %(username)s:%(password)s https://%(device)s/mgmt/tm/ltm/pool/"
F5_LTM_POOL_CURL_URL = F5_LTM_POOL + " -H 'Content-Type: application/json'"
F5_LTM_POOL_POST_CURL_URL = F5_LTM_POOL_CURL_URL + " -X POST -d "

# default parameter values
VIRTUALSERVER_DEFAULT_SETTING_PERFORML4_TCP_PERSIST = "\"name\":\"%(virtualservername)s\",\"destination\":\"%(destination)s\",\"ip-protocol\":\"tcp\",\"pool\":\"%(poolname)s\",\"profiles\":[%(profiles_option)s],\"persist\":[%(persist_option)s],\"mirror\":\"enabled\",\"translatePort\":\"enabled\""

POOL_DEFAULT_SETTING_ROUNDROBIN = "\"name\":\"%(poolname)s\",\"members\":\"%(poolmembers)s\",\"serviceDownAction\":\"reset\",\"loadBalancingMode\":\"round-robin\""

VIRTUALSERVER_CREATE_CMD_FORMAT = [
                                    {
                                      "device":["10.10.77.29","10.10.77.30","10.10.77.45","10.10.77.46"],
                                      "created_command":F5_LTM_VIRTUAL_POST_CURL_URL + "'{"+VIRTUALSERVER_DEFAULT_SETTING_PERFORML4_TCP_PERSIST+",\"translateAddress\":\"enabled\",\"rules\":[\"/Common/vip_from_was_web_snatpool\"],\"sourceAddressTranslation\":{}"+"}'"
                                    },
                                    {
                                      "device":["10.10.77.31","10.10.77.32","10.10.77.33","10.10.77.34"],
                                      "created_command":F5_LTM_VIRTUAL_POST_CURL_URL + "'{"+VIRTUALSERVER_DEFAULT_SETTING_PERFORML4_TCP_PERSIST+",\"translateAddress\":\"enabled\",\"rules\":[],\"sourceAddressTranslation\":{\"type\":\"automap\"}"+"}'"
                                    },
                                    {
                                      "device":["10.10.30.101","10.10.30.102"],
                                      "created_command":F5_LTM_VIRTUAL_POST_CURL_URL + "'{"+VIRTUALSERVER_DEFAULT_SETTING_PERFORML4_TCP_PERSIST+",\"translateAddress\":\"disabled\",\"rules\":[],\"sourceAddressTranslation\":{\"type\":\"none\"}"+"}'"
                                    }
                                  ]

POOL_CREATE_CMD_FORMAT = [
                           {
                             "device":["10.10.77.29","10.10.77.30","10.10.77.31","10.10.77.32","10.10.77.33","10.10.77.34","10.10.77.45","10.10.77.46","10.10.30.101","10.10.30.102"],
                             "created_command":F5_LTM_POOL_POST_CURL_URL + "'{"+POOL_DEFAULT_SETTING_ROUNDROBIN+",\"monitor\":\"/Common/tcp_skp\""+"}'"
                           }
                         ]

COMMOM_CMD_FORMAT = {
                      "delete_pool_command":F5_LTM_POOL + "%(poolname)s -H 'Content-Type: application/json' -X DELETE",
                      "delete_virtualserver_command":F5_LTM_VIRTUAL + "%(virtualservername)s -H 'Content-Type: application/json' -X DELETE",
                      "sync_command":"curl -sk -u %(username)s:%(password)s https://%(device)s/mgmt/tm/ltm/pool/ -H 'Content-Type: application/json' -X POST -d '{\"command\":\"run\",\"utilCmdArgs\":\"config-sync to-group %(syncgroup)s\"}'"
                    }



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
def f5_create_config_lb(request,format=None):

   # get method
   if request.method == 'GET':

      # get the result data and return
##[
##    {
##        "items": [
##            {
##                "device": "KRIS10-PUBS01-5000L4 or 10.10.77.29",
##                "poolmembers": [
##                    "172.22.192.251:8080",
##                    "172.22.192.252:8080",
##                    "172.22.192.253:8080"
##                ],
##                "servername": "OCBPASS_WEB",
##                "virtual_ip_port": "172.22.198.254:8080",
##                "options": [
##                    "sticky"
##                ]
##            },
##            {}
##        ],
##        "auth_key": "Adfakladjfqern@sdfjlaf1!"
##    }
##]


      message = [{
                   "items":[
                               {
                                 "virtual_ip_port":"172.22.198.254:8080",
                                 "device":"KRIS10-PUBS01-5000L4 or 10.10.77.29",
                                 "servername":"OCBPASS_WEB",
                                 "poolmembers":["172.22.192.251:8080","172.22.192.252:8080","172.22.192.253:8080"],
                                 "options":["sticky"]
                                },
                                {
                                }  
                            ]
                 }]



      return Response(message)


   elif request.method == 'POST':

      try:

        _input_ = JSONParser().parse(request)

        
        if re.match(ENCAP_PASSWORD,str(_input_[0]['auth_key'])):


           message = [] 

           # log message
           f = open(LOG_FILE,"a")
           _date_ = os.popen("date").read().strip()
           log_msg = _date_+" from : "+request.META['REMOTE_ADDR']+" , method POST request to run f5_create_config_lb.py function!\n"
           f.write(log_msg)
           f.close()

           # input variable check
           _musthave_key_ = [u'device',u'poolmembers',u'servername',u'virtual_ip_port']
           for _loop1_ in _input_[0][u'items']:
              for _loop2_ in _musthave_key_:
                 if _loop2_ not in _loop1_.keys():
                   f = open(LOG_FILE,"a")
                   _date_ = os.popen("date").read().strip()
                   log_msg = _date_+" from : "+request.META['REMOTE_ADDR']+" , parameter ["+str(_loop2_)+"] is required !\n"
                   f.write(log_msg)
                   f.close()
                   # terminated
                   sys.exit(0)

           # read device list file
           _devicelist_db_ = USER_DATABASES_DIR + "devicelist.txt"
           f = open(_devicelist_db_,'r')
           _string_contents_ = f.readlines()
           f.close()
           stream = BytesIO(_string_contents_[0])
           _data_from_file_ = JSONParser().parse(stream)
           _data_from_devicelist_db_  = copy.copy(_data_from_file_)

           # user data input values
           _user_input_data_ = copy.copy(_input_[0][u'items'])

           # device input will be exchanged to the active device ip address
           # _user_input_data_device_ip_changed_ is list form 
           _user_input_data_device_ip_changed_ = []
           copy_loop_param = copy.copy(_user_input_data_)
           for _loop1_ in copy_loop_param:
              _device_input_ = str(_loop1_[u'device'])
           
              _target_device_ip_ = '' 
              if re.search("[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+",_device_input_):
                for _loop2_ in _data_from_devicelist_db_:
                   if re.search(str(_device_input_),str(_loop2_[u'ip'])):
                      if re.search(str('active'),(_loop2_[u'failover'])):
                         _target_device_ip_ = str(_loop2_[u'ip'])
                         break
                      else:
                         _object_ = str(_loop2_[u'haclustername'])
                         for _loop3_ in _data_from_devicelist_db_:
                            if re.search(_object_,str(_loop3_[u'clustername'])):
                              _target_device_ip_ = str(_loop3_[u'ip'])
                              break
              else:
                for _loop2_ in _data_from_devicelist_db_:
                   if re.search(_device_input_,str(_loop2_[u'devicehostname'])) or re.search(_device_input_,str(_loop2_[u'clustername'])):
                      if re.search(str('active'),(_loop2_[u'failover'])):
                         _target_device_ip_ = str(_loop2_[u'ip'])
                         break
                      else:
                         _object_ = str(_loop2_[u'haclustername'])
                         for _loop3_ in _data_from_devicelist_db_:
                            if re.search(_object_,str(_loop3_[u'clustername'])):
                              _target_device_ip_ = str(_loop3_[u'ip'])
                              break
                   else:
                      _object_ = str(_loop2_[u'haclustername'])
                      for _loop3_ in _data_from_devicelist_db_:
                         if re.search(_object_,str(_loop3_[u'clustername'])):
                           _target_device_ip_ = str(_loop3_[u'ip'])
                           break

              if re.match('',str(_target_device_ip_)):
                _loop1_[u'device'] = _target_device_ip_
                _user_input_data_device_ip_changed_.append(_loop1_)

           # virtual ip address confirmation
           # virtual ip address should be unique according to the device.
           # input : _user_input_data_device_ip_changed_ (device ip exchanged data)
           # output : _user_input_data_virtualipport_unique_
           _temp_dictbox_ = {}
           for _loop1_ in _user_input_data_device_ip_changed_:
              if str(_loop1_[u'device']) not in _temp_dictbox_.keys():
                _temp_dictbox_[str(_loop1_[u'device'])] = {}

           for _loop1_ in _user_input_data_device_ip_changed_:
              if str(_loop1_[u'virtual_ip_port']) not in _temp_dictbox_[str(_loop1_[u'device'])].keys():
                _temp_dictbox_[str(_loop1_[u'device'])][str(_loop1_[u'virtual_ip_port'])] = int(1) 
              else:
                _temp_dictbox_[str(_loop1_[u'device'])][str(_loop1_[u'virtual_ip_port'])] = _temp_dictbox_[str(_loop1_[u'device'])][str(_loop1_[u'virtual_ip_port'])] + int(1)

           _user_input_data_virtualipport_unique_ = []
           for _loop1_ in _user_input_data_device_ip_changed_:
              if _temp_dictbox_[str(_loop1_[u'device'])][str(_loop1_[u'virtual_ip_port'])] == int(1):
                _user_input_data_virtualipport_unique_.append(_loop1_)  

           # find out the database file name
           for _loop1_ in _user_input_data_virtualipport_unique_:
              for _loop2_ in _data_from_devicelist_db_:
                 if re.search(str(_loop1_[u'device']),str(_loop2_[u'ip'])):
                   _loop1_[u'syncgroup'] = str(_loop2_[u'devicegroupname'])
                   for _loop3_ in _data_from_devicelist_db_:
                      if re.match(str(_loop2_[u'haclustername']),str(_loop3_[u'clustername'])):
                        _loop1_[u'pairdevice'] = str(_loop3_[u'ip'])
           
           # virtual server ip port usage confirmation
           # this step will be find out the virtual server usage according to the virtual server ip and port information
           # _user_input_data_virtualipport_unique_ will be updated.
           for _loop1_ in _user_input_data_virtualipport_unique_:
              database_filename = USER_DATABASES_DIR+"virtualserverlist."+str(_loop1_[u'pairdevice'])+".txt"
              f = open(database_filename,"r")
              _contents_ = f.readlines()
              f.close()
              stream = BytesIO(_contents_[0])
              data_from_file = JSONParser().parse(stream)

              _loop1_[u'virtualserver_names_list'] = []
              for _loop2_ in data_from_file[u'items']:
                 if re.search(str(_loop1_[u'virtual_ip_port']),str(_loop2_[u'destination'])):
                   _loop1_[u'virtualserver_names_list'].append(str(_loop2_[u'fullPath']))
            
           # node usage confirmation
           # pool information will be necessary according to node information
           # _user_input_data_virtualipport_unique_ : virtual ip port is checked

           _user_input_data_nodes_confirm_ = copy.copy(_user_input_data_virtualipport_unique_) 
           _temp_traybox_ = {}
           for _loop1_ in _user_input_data_nodes_confirm_:
              if str(_loop1_[u'device']) not in _temp_traybox_.keys():
                _temp_traybox_[str(_loop1_[u'device'])] = {}

           for _loop1_ in _user_input_data_nodes_confirm_:
              for _loop2_ in _loop1_[u'poolmembers']:
                 _temp_traybox_[str(_loop1_[u'device'])][str(_loop2_)] = []

           for _loop1_ in _user_input_data_nodes_confirm_:
              for _loop2_ in _loop1_[u'poolmembers']:
                 database_filename = USER_DATABASES_DIR+"poollist."+str(_loop1_[u'pairdevice'])+".txt"
                 f = open(database_filename,"r")
                 _contents_ = f.readlines()
                 f.close()
                 stream = BytesIO(_contents_[0])
                 data_from_file = JSONParser().parse(stream)
                 
                 for _loop3_ in data_from_file[u'items']:
                    for _loop4_ in _loop3_[u'poolmembers_status_list']:
                       if re.search(str(_loop2_),str(_loop4_)):
                          _temp_traybox_[str(_loop1_[u'device'])][str(_loop2_)].append(str(_loop3_[u'name']))

           for _loop1_ in _user_input_data_nodes_confirm_:
              _temp_dictbox_ = {}
              for _loop2_ in _loop1_[u'poolmembers']:
                 for _loop3_ in _temp_traybox_[str(_loop1_[u'device'])][str(_loop2_)]:
                    if str(_loop3_) not in _temp_dictbox_.keys():
                      _temp_dictbox_[str(_loop3_)] = int(1)
                    else:
                      _temp_dictbox_[str(_loop3_)] = _temp_dictbox_[str(_loop3_)] + int(1)
              _temp_listbox_ = [] 
              for _loop2_ in _temp_dictbox_.keys():
                 if int(_temp_dictbox_[_loop2_]) == int(len(_loop1_[u'poolmembers'])):
                   if str(_loop2_) not in _temp_listbox_:
                     _temp_listbox_.append(str(_loop2_))
              _loop1_[u'poolnames_list'] = _temp_listbox_
                                        
           for _loop1_ in _user_input_data_nodes_confirm_:
              _temp_listbox_ = []
              for _loop2_ in _loop1_[u'poolnames_list']:
                 database_filename = USER_DATABASES_DIR+"poollist."+str(_loop1_[u'pairdevice'])+".txt"
                 f = open(database_filename,"r")
                 _contents_ = f.readlines()
                 f.close()
                 stream = BytesIO(_contents_[0])
                 data_from_file = JSONParser().parse(stream)
                 for _loop3_ in data_from_file[u'items']:
                    if re.search(str(_loop2_),str(_loop3_[u'name'])) and len(_loop1_[u'poolmembers']) == len(_loop3_[u'poolmembers_status_list']):
                      if str(_loop3_[u'name']) not in _temp_listbox_:
                        _temp_listbox_.append(str(_loop3_[u'name']))
              _loop1_[u'poolnames_list'] = _temp_listbox_

           # virtual server and pool name creation
           # _user_input_data_nodes_confirm_ : perfect varidation checked
           # virtual server information should be empty to create something new one.
           _valid_user_input_data_ = []
           for _loop1_ in _user_input_data_nodes_confirm_:
              if len(_loop1_[u'virtualserver_names_list']) != int(0):
                # log message
                f = open(LOG_FILE,"a")
                _date_ = os.popen("date").read().strip()
                log_msg = _date_+" from : "+request.META['REMOTE_ADDR']+" virtual ip port : "+str(_loop1_[u'virtual_ip_port'])+", assigned virtual server :  "+str(','.join(_loop1_[u'virtualserver_names_list']))+" !\n"
                f.write(log_msg)
                f.close()
              else:
                _valid_user_input_data_.append(_loop1_)

           # command creation and f5 rest_api command
           # virtual server name should be empty
           # _valid_user_input_data_ : is full varified data

           #for _loop1_ in _valid_user_input_data_:
           #   _loop1_[u'configCmd'] = {}

           _return_message_list_ = []
           for _loop1_ in _valid_user_input_data_:
              if len(_loop1_[u'virtualserver_names_list']) == int(0):

                 # Parameter re-arrange
                 info_in_pairdevice = _loop1_[u'pairdevice']
                 info_in_poolnames_list = _loop1_[u'poolnames_list']
                 info_in_virtual_ip_port = _loop1_[u'virtual_ip_port']
                 info_in_servername = _loop1_[u'servername']
                 info_in_poolmembers = _loop1_[u'poolmembers']
                 info_in_device = _loop1_[u'device']
                 info_in_syncgroup = _loop1_[u'syncgroup']

                 ### server name recreation
                 SERVERHOST_name = str('_'.join(info_in_servername.strip().split('-')))

                 ### option check confirmation
                 ### this part will be upgrade if you add new option
                 ###
                 info_in_sticky = ""
                 if u'options' in _loop1_.keys():
                   # option : sticky
                   if u'sticky' in _loop1_[u'options']:
                     for _loop2_ in DEFAULT_SETTING:
                        if str(info_in_device) in _loop2_['device']:
                          info_in_sticky = _loop2_['sticky']
                          break 

                 ### option check confirmation
                 info_in_profiles = ""
                 for _loop2_ in DEFAULT_SETTING:
                    if str(info_in_device) in _loop2_['device']:
                      info_in_profiles = _loop2_['profiles']
                      break
   
                 # find out the command format to create the pool
                 command_format_to_pool = {}
                 for _loop2_ in POOL_CREATE_CMD_FORMAT:
                    if str(info_in_device) in _loop2_["device"]:
                      command_format_to_pool[u'create'] = _loop2_["created_command"]
                      command_format_to_pool[u'delete'] = COMMOM_CMD_FORMAT["delete_pool_command"]
                      break

                 command_format_to_virtualserver = {}
                 for _loop2_ in VIRTUALSERVER_CREATE_CMD_FORMAT:
                    if str(info_in_device) in _loop2_["device"]:
                      command_format_to_virtualserver[u'create'] = _loop2_["created_command"]
                      command_format_to_virtualserver[u'delete'] = COMMOM_CMD_FORMAT["delete_virtualserver_command"]
                      break

                 # create the pool name new and update the pool name and create command
                 _temp_box_ = []
                 _temp_string_box_ = []
                 for _loop2_ in _loop1_[u'poolmembers']:
                    _string_value_ = str(_loop2_).strip()
                    _port_info_ = str(_string_value_.split(':')[-1])
                    if str(_port_info_) not in _temp_box_:
                      _temp_box_.append(str(_port_info_))
                    if str(_string_value_) not in _temp_string_box_:
                      _temp_string_box_.append(str(_string_value_))
                 _name_with_ports_ = str("_".join(_temp_box_)) 
                 _poolmember_string_ = str(" ".join(_temp_string_box_))
                 _poolname_created_ = "p_%(servername)s_%(portname)s" % {"servername":SERVERHOST_name,"portname":_name_with_ports_}

                 # create virtual server
                 _splited_ip_ = str(_loop1_[u'virtual_ip_port']).strip().split(':')[0]
                 _splited_port_ = str(_loop1_[u'virtual_ip_port']).strip().split(':')[-1]
                 _rename_ip_value_ = str('.'.join(str(_splited_ip_).split('.')[int(VIRTUALIP_SPLITE_COUNT):]))
                 _virtualservername_created_ = "v_%(ipport)s_%(servername)s_%(portname)s" % {"ipport":_rename_ip_value_,"servername":SERVERHOST_name,"portname":_splited_port_}


                 # create the diction value for input
                 _string_formatting_dictionary_ = {
                                                    "username":USER_NAME,
                                                    "password":USER_PASSWORD,
                                                    "device":str(info_in_device),
                                                    "poolname":str(_poolname_created_),
                                                    "virtualservername":str(_virtualservername_created_),
                                                    "syncgroup":str(info_in_syncgroup),
                                                    "destination":str(info_in_virtual_ip_port),
                                                    "poolmembers":str(_poolmember_string_),
                                                    "persist_option":str(info_in_sticky),
                                                    "profiles_option":str(info_in_profiles)
                                                  }

                 ### F5 curl command creation and log messeges left
                 _F5_POOL_create_ = command_format_to_pool[u'create'] % _string_formatting_dictionary_
                 _F5_POOL_delete_ = command_format_to_pool[u'delete'] % _string_formatting_dictionary_
                 _F5_VIRTUAL_Server_create_ = command_format_to_virtualserver[u'create'] % _string_formatting_dictionary_
                 _F5_VIRTUAL_Server_delete_ = command_format_to_virtualserver[u'delete'] % _string_formatting_dictionary_

                 f = open(LOG_FILE,"a")
                 _date_ = os.popen("date").read().strip()
                 for _loop2_ in [_F5_POOL_create_,_F5_POOL_delete_,_F5_VIRTUAL_Server_create_,_F5_VIRTUAL_Server_delete_]:
                    log_msg = _date_+" from : "+request.META['REMOTE_ADDR']+" , COMMAND :["+_loop2_+"]!\n"
                    f.write(log_msg)
                 f.close()

                 ## 
                 _final_command_ = {
                                     "create":[_F5_POOL_create_,_F5_VIRTUAL_Server_create_],
                                     "delete":[_F5_POOL_delete_,_F5_VIRTUAL_Server_delete_]
                                   }
                 _return_message_list_.append(_final_command_)

           message = _return_message_list_ 
           return Response(message)


      except:
        message = [{}]
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

