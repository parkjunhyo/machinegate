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

#### naming rule
VIP_NAME_OPTION = [
                    {
                      "device":["10.10.77.29","10.10.77.30","10.10.77.45","10.10.77.46","10.10.30.101","10.10.30.102","10.10.77.31","10.10.77.32","10.10.77.33","10.10.77.34"],
                      "name_string": "v_%(ipport)s_%(servername)s_%(portname)s",
                      "VIRTUALIP_SPLITE_COUNT":int(2)
                    },
                    {
                      "device":["172.18.177.101","172.18.177.102","172.18.177.103","172.18.177.104","172.18.177.105","172.18.177.106"],
                      "name_string": "vs_%(ipport)s_%(portname)s",
                      "VIRTUALIP_SPLITE_COUNT":int(0)
                    } 
                  ]

PORT_NAME_OPTION = [
                    {
                      "device":["10.10.77.29","10.10.77.30","10.10.77.45","10.10.77.46","10.10.30.101","10.10.30.102","10.10.77.31","10.10.77.32","10.10.77.33","10.10.77.34"],
                      "name_string": "p_%(servername)s_%(portname)s"
                    },
                    {
                      "device":["172.18.177.101","172.18.177.102","172.18.177.103","172.18.177.104","172.18.177.105","172.18.177.106"],
                      "name_string": "p_%(ipport)s_%(portname)s"
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
                                    },
                                    {
                                      "device":["172.18.177.101","172.18.177.102","172.18.177.103","172.18.177.104","172.18.177.105","172.18.177.106"],
                                      "created_command":F5_LTM_VIRTUAL_POST_CURL_URL + "'{"+VIRTUALSERVER_DEFAULT_SETTING_PERFORML4_TCP_PERSIST+",\"translateAddress\":\"enabled\",\"rules\":[],\"sourceAddressTranslation\":{\"type\":\"none\"}"+"}'"
                                    }
                                  ]

POOL_CREATE_CMD_FORMAT = [
                           {
                             "device":["10.10.77.29","10.10.77.30","10.10.77.31","10.10.77.32","10.10.77.33","10.10.77.34","10.10.77.45","10.10.77.46","10.10.30.101","10.10.30.102"],
                             "created_command":F5_LTM_POOL_POST_CURL_URL + "'{"+POOL_DEFAULT_SETTING_ROUNDROBIN+",\"monitor\":\"/Common/tcp_skp\""+"}'"
                           },
                           {
                             "device":["172.18.177.101","172.18.177.102","172.18.177.103","172.18.177.104","172.18.177.105","172.18.177.106"],
                             "created_command":F5_LTM_POOL_POST_CURL_URL + "'{"+POOL_DEFAULT_SETTING_ROUNDROBIN+",\"monitor\":\"/Common/my_tcp\""+"}'"
                           }
                         ]

COMMOM_CMD_FORMAT = {
                      "delete_pool_command":F5_LTM_POOL + "%(poolname)s -H 'Content-Type: application/json' -X DELETE",
                      "delete_virtualserver_command":F5_LTM_VIRTUAL + "%(virtualservername)s -H 'Content-Type: application/json' -X DELETE",
                      "sync_command":"curl -sk -u %(username)s:%(password)s https://%(device)s/mgmt/tm/ltm/pool/ -H 'Content-Type: application/json' -X POST -d '{\"command\":\"run\",\"utilCmdArgs\":\"config-sync to-group %(syncgroup)s\"}'"
                    }


## CONFGURATION SETTING
CONFIG_OPTION_SETTING_VALUE = [
 {
  "device":["10.10.77.29","10.10.77.30","10.10.77.45","10.10.77.46"],
  "sticky":"{\"name\":\"source_addr_300\"}",
  "profiles":"\"fastL4\"",
  "portforward":False,
  "format_to_create_pool":F5_LTM_POOL_POST_CURL_URL + "'{"+POOL_DEFAULT_SETTING_ROUNDROBIN+",\"monitor\":\"/Common/tcp_skp\""+"}'"
 },
 {
  "device":["10.10.30.101","10.10.30.102"],
  "sticky":"{\"name\":\"source_addr_300\"}",
  "profiles":"\"fastL4_loose\"",
  "portforward":False,
  "format_to_create_pool":F5_LTM_POOL_POST_CURL_URL + "'{"+POOL_DEFAULT_SETTING_ROUNDROBIN+",\"monitor\":\"/Common/tcp_skp\""+"}'"
 },
 {
  "device":["10.10.77.31","10.10.77.32","10.10.77.33","10.10.77.34"],
  "sticky":"",
  "profiles":"\"fastL4\"",
  "portforward":False,
  "format_to_create_pool":F5_LTM_POOL_POST_CURL_URL + "'{"+POOL_DEFAULT_SETTING_ROUNDROBIN+",\"monitor\":\"/Common/tcp_skp\""+"}'"
 },
 {
  "device":["172.18.177.101","172.18.177.102","172.18.177.103","172.18.177.104","172.18.177.105","172.18.177.106"],
  "sticky":"{\"name\":\"my_src_persist\"}",
  "profiles":"\"fastL4\"",
  "portforward":False,
  "format_to_create_pool":F5_LTM_POOL_POST_CURL_URL + "'{"+POOL_DEFAULT_SETTING_ROUNDROBIN+",\"monitor\":\"/Common/my_tcp\""+"}'"
 }
]



class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders its content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)


getview_message = [{
                   "items":[
                               ## Basci Parameter (Must Have, essencial values)
                               {
                                 "virtual_ip_port":"172.22.198.252:443",
                                 "device":"KRIS10-PUBS01-5000L4 or 10.10.77.29",
                                 "servername":"SYRUPWALLET",
                                 "poolmembers":["172.22.192.240:443","172.22.192.241:443"]
                                },
                               ## Option added Parameter
                                {
                                 "virtual_ip_port":"172.22.198.254:8080",
                                 "device":"KRIS10-PUBS01-5000L4 or 10.10.77.29",
                                 "servername":"OCBPASS_WEB",
                                 "poolmembers":["172.22.192.251:8080","172.22.192.252:8080","172.22.192.253:8080"],
                                 "options":["sticky"]
                                }
                            ]
                   }]

  

@api_view(['GET','POST'])
@csrf_exempt
def f5_create_config_lb(request,format=None):

   # get method
   if request.method == 'GET':

      message = getview_message 
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

           # This part will check the essecial parameters (this use the first value in getview_message parameter)
           _musthave_key_ = []
           for _dictitem_ in getview_message[0]["items"]:
              for _item_ in _dictitem_.keys():
                 unicode_item = unicode(_item_)
                 if unicode("options") != unicode_item:
                   if unicode_item not in _musthave_key_:
                     _musthave_key_.append(unicode_item)

           # This part will be check the essencial parametes with input data values
           input_inform_items_list = _input_[0][u'items']
           for element_dict in input_inform_items_list:
              element_keynames_list = element_dict.keys()
              element_keynames_list_string = []
              for _elem_ in element_keynames_list:
                 if str(_elem_) not in element_keynames_list_string:
                   element_keynames_list_string.append(str(_elem_))
              for ess_keyname in _musthave_key_:
                 ess_keyname_string = str(ess_keyname)
                 if ess_keyname_string not in element_keynames_list_string:
                   message = "%(ess_keyname_string)s is not existed from input datas" % {"ess_keyname_string":ess_keyname_string} 
                   return Response(message, status=status.HTTP_400_BAD_REQUEST)

           ## 2016.12.06
           CURL_command = "curl http://0.0.0.0:"+RUNSERVER_PORT+"/f5/devicelist/"
           get_info = os.popen(CURL_command).read().strip()
           stream = BytesIO(get_info)
           _data_from_devicelist_db_ = JSONParser().parse(stream)

           ## Read the devices list database file.
           #_devicelist_db_ = USER_DATABASES_DIR + "devicelist.txt"
           #f = open(_devicelist_db_,'r')
           #_string_contents_ = f.readlines()
           #f.close()
           #stream = BytesIO(_string_contents_[0])
           #_data_from_file_ = JSONParser().parse(stream)
           #_data_from_devicelist_db_  = copy.copy(_data_from_file_)

           ######### start ###########
           _user_input_data_ = copy.copy(input_inform_items_list)


           _user_input_data_device_ip_changed_ = []
           copy_loop_param = copy.copy(_user_input_data_)


           for _loop1_ in copy_loop_param:
              _device_input_ = str(_loop1_[u'device'])
              ## this value is the target ip address : active device ip address
              _target_device_ip_ = None 
              search_re = re.search("([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)",_device_input_,re.I)
              if search_re:
                # input device information will be ip address                
                devicename_status = None
                searched_re_ip = str(search_re.groups()[0])
                for _loop2_ in _data_from_devicelist_db_:
                   if re.search(searched_re_ip,str(_loop2_[u'ip'])):
                      if re.search(str('active'),(_loop2_[u'failover'])):
                         _target_device_ip_ = str(_loop2_[u'ip'])
                         devicename_status = True
                         break
                      else:
                         _object_ = str(_loop2_[u'haclustername'])
                         for _loop3_ in _data_from_devicelist_db_:
                            if re.search(_object_,str(_loop3_[u'clustername'])):
                              _target_device_ip_ = str(_loop3_[u'ip'])
                              devicename_status = True
                              break
                if not devicename_status:
                   message = "the device name [%(_device_input_)s] is not in the device list!" % {"_device_input_":str(_device_input_)}
                   return Response(message, status=status.HTTP_400_BAD_REQUEST)
              else:
                # input device information will be name 
                devicename_status = None
                for _loop2_ in _data_from_devicelist_db_:
                   search_re_devicehostname = re.search(_device_input_,str(_loop2_[u'devicehostname']),re.I)
                   search_re_clustername = re.search(_device_input_,str(_loop2_[u'clustername']),re.I)
                   if search_re_devicehostname or search_re_clustername:
                      if re.search(str('active'),(_loop2_[u'failover']),re.I):
                         _target_device_ip_ = str(_loop2_[u'ip'])
                         devicename_status = True
                         break
                      else:
                         _object_ = str(_loop2_[u'haclustername'])
                         for _loop3_ in _data_from_devicelist_db_:
                            if re.search(_object_,str(_loop3_[u'clustername']),re.I):
                              _target_device_ip_ = str(_loop3_[u'ip'])
                              devicename_status = True
                              break
                if not devicename_status:
                   message = "the device name [%(_device_input_)s] is not in the device list!" % {"_device_input_":str(_device_input_)}
                   return Response(message, status=status.HTTP_400_BAD_REQUEST)
              # this part will change the device information as the active device ip address
              if _target_device_ip_:
                _loop1_[u'device'] = _target_device_ip_
                _user_input_data_device_ip_changed_.append(_loop1_)
              else:
                return Response("error, device name is not proper, please check your input or device list!", status=status.HTTP_400_BAD_REQUEST)

           ## This part will check the this operation policy is allow that port Forwarding is enable
           for _item_dict_ in _user_input_data_device_ip_changed_:
              active_device_ipaddr = str(_item_dict_[u'device'])
              for _dict_value_ in CONFIG_OPTION_SETTING_VALUE:
                 if (str(active_device_ipaddr) in _dict_value_["device"]) or (unicode(active_device_ipaddr) in _dict_value_["device"]):
                   port_forward_status = _dict_value_["portforward"] 
                   break
              if not port_forward_status:
                 virtualport = str(_item_dict_[u'virtual_ip_port']).strip().split(":")[-1]
                 realport = []
                 for _dict_ in _item_dict_[u'poolmembers']:
                    portservice = str(_dict_).strip().split(":")[-1]
                    if portservice not in realport:
                      realport.append(portservice)
                 if len(realport) != 1:
                    realport_string = str(",".join(realport))
                    message = "port forwarding is not allow, real server port use [%(realport_string)s], not matched!" % {"realport_string":str(realport_string)}
                    return Response(message, status=status.HTTP_400_BAD_REQUEST)
                 if not re.match(virtualport,realport[-1],re.I):
                    message = "port forwarding is not allow, virtual port [%(virtualport)s], server port [%(realport)s]!" % {"virtualport":str(virtualport),"realport":str(realport[-1])}
                    return Response(message, status=status.HTTP_400_BAD_REQUEST)
                 # port forward status confirmation
                 _item_dict_[u'portforward_status'] = False 
              else:
                 _item_dict_[u'portforward_status'] = True

           # check if virtual ip address of input values is unique
           _temp_dictbox_ = {}
           for _loop1_ in _user_input_data_device_ip_changed_:
              if str(_loop1_[u'device']) not in _temp_dictbox_.keys():
                _temp_dictbox_[str(_loop1_[u'device'])] = {}
           for _loop1_ in _user_input_data_device_ip_changed_:
              _mydeviceinfo_ = str(_loop1_[u'device'])
              _myvipinfo_ = str(_loop1_[u'virtual_ip_port'])
              if _myvipinfo_ not in _temp_dictbox_[_mydeviceinfo_].keys():
                _temp_dictbox_[_mydeviceinfo_][_myvipinfo_] = int(1) 
              else:
                _temp_dictbox_[_mydeviceinfo_][_myvipinfo_] = _temp_dictbox_[_mydeviceinfo_][_myvipinfo_] + int(1)
           # this is unique value
           _user_input_data_virtualipport_unique_ = []
           for _loop1_ in _user_input_data_device_ip_changed_:
              _mydeviceinfo_ = str(_loop1_[u'device'])
              _myvipinfo_ = str(_loop1_[u'virtual_ip_port'])
              if _temp_dictbox_[_mydeviceinfo_][_myvipinfo_] == int(1):
                _user_input_data_virtualipport_unique_.append(_loop1_)  
              else:
                message = "input virtual ip and port [%(dup_viport)s] is duplicated!" % {"dup_viport":_myvipinfo_}
                return Response(message, status=status.HTTP_400_BAD_REQUEST)

           # Using the Backup database file, We want to search the usage of the virtual server ip address and port
           # backup information will be updated to sync
           for _loop1_ in _user_input_data_virtualipport_unique_:
              for _loop2_ in _data_from_devicelist_db_:
                 if re.search(str(_loop1_[u'device']),str(_loop2_[u'ip']),re.I):
                   _loop1_[u'syncgroup'] = str(_loop2_[u'devicegroupname'])
                   for _loop3_ in _data_from_devicelist_db_:
                      if re.search(str(_loop2_[u'haclustername']),str(_loop3_[u'clustername']),re.I):
                        _loop1_[u'pairdevice'] = str(_loop3_[u'ip'])
           
           # virtual server ip port usage confirmation
           # this step will be find out the virtual server usage according to the virtual server ip and port information
           # _user_input_data_virtualipport_unique_ will be updated.

           CURL_command = "curl http://0.0.0.0:"+RUNSERVER_PORT+"/f5/virtualserverlist/"
           get_info = os.popen(CURL_command).read().strip()
           stream = BytesIO(get_info)
           _data_from_virtualserver_db_ = JSONParser().parse(stream)

           for _loop1_ in _user_input_data_virtualipport_unique_:
              #database_filename = USER_DATABASES_DIR+"virtualserverlist."+str(_loop1_[u'pairdevice'])+".txt"
              #f = open(database_filename,"r")
              #_contents_ = f.readlines()
              #f.close()
              #stream = BytesIO(_contents_[0])
              #data_from_file = JSONParser().parse(stream)

              compvipport = str(_loop1_[u'virtual_ip_port'])
              pairdevicename = str(_loop1_[u'pairdevice'])
              for _dict_virtualinfo_ in _data_from_virtualserver_db_:
                 _keynamelist_ = _dict_virtualinfo_.keys()
                 for _keyname_ in _keynamelist_:
                    _searched_vipinfo_ = str(_dict_virtualinfo_[_keyname_][u'destination'])
                    parsed_searched_vipinfo = str(_searched_vipinfo_.strip().split("/")[-1])
                    if re.search(compvipport,_searched_vipinfo_,re.I) or re.search(compvipport,parsed_searched_vipinfo,re.I):
                      message = "input virtual ip and port [%(compvipport)s] has already used on [%(pairdevicename)s]" % {"compvipport":compvipport,"pairdevicename":pairdevicename}
                      return Response(message, status=status.HTTP_400_BAD_REQUEST)

            
           # node usage confirmation
           # pool information will be necessary according to node information
           # _user_input_data_virtualipport_unique_ : virtual ip port is checked
           CURL_command = "curl http://0.0.0.0:"+RUNSERVER_PORT+"/f5/poolmemberlist/"
           get_info = os.popen(CURL_command).read().strip()
           stream = BytesIO(get_info)
           _data_from_poolmemberlist_api_ = JSONParser().parse(stream)


           _user_input_data_nodes_confirm_ = copy.copy(_user_input_data_virtualipport_unique_) 
           _temp_traybox_ = {}

           for _loop1_ in _user_input_data_nodes_confirm_:
              if str(_loop1_[u'device']) not in _temp_traybox_.keys():
                _temp_traybox_[str(_loop1_[u'device'])] = {}

           for _loop1_ in _user_input_data_nodes_confirm_:
              _thisdevice_ = str(_loop1_[u'device'])
              _mypoolmemberslist_ = _loop1_[u'poolmembers'] 
              for _loop2_ in _mypoolmemberslist_:
                 _mypoolmemberinfo_ = str(_loop2_)
                 _temp_traybox_[_thisdevice_][_mypoolmemberinfo_] = []

           for _loop1_ in _user_input_data_nodes_confirm_:
              _thispairdevice_ = str(_loop1_[u'pairdevice'])
              _thisdevice_ = str(_loop1_[u'device'])
              _mypoolmemberslist_ = _loop1_[u'poolmembers']
              if unicode(_thispairdevice_) not in _data_from_poolmemberlist_api_.keys():
                message = "%(_thispairdevice_)s or %(_thisdevice_)s poolmemberlist is not existed!" % {"_thispairdevice_":_thispairdevice_,"_thisdevice_":_thisdevice_}
                return Response(message, status=status.HTTP_400_BAD_REQUEST)

              for _loop2_ in _mypoolmemberslist_:

                 #database_filename = USER_DATABASES_DIR+"poollist."+str(_loop1_[u'pairdevice'])+".txt"
                 #f = open(database_filename,"r")
                 #_contents_ = f.readlines()
                 #f.close()
                 #stream = BytesIO(_contents_[0])
                 #data_from_file = JSONParser().parse(stream)

                 _inputipport_info_ = str(_loop2_)
                 _data_from_poolmemberlist_api_keyname_ = _data_from_poolmemberlist_api_[unicode(_thispairdevice_)].keys()
                 for _keyname_ in _data_from_poolmemberlist_api_keyname_:
                    _keyname_string_ = str(_keyname_)
                    _memberitem_list_ = _data_from_poolmemberlist_api_[unicode(_thispairdevice_)][_keyname_string_][u'poolmembers_status']
                    for _memberitem_ in _memberitem_list_:
                       temp_parse_ipport_info = str(str(_memberitem_).strip().split("/")[-1])
                       if re.match(_inputipport_info_,temp_parse_ipport_info,re.I) and (len(_inputipport_info_)==len(temp_parse_ipport_info)):
                         _temp_traybox_[_thisdevice_][_inputipport_info_].append(_keyname_string_)
                    

                 
                 #for _loop3_ in data_from_file[u'items']:
                 #   for _loop4_ in _loop3_[u'poolmembers_status_list']:
                 #      temp_parse_ipport_info = str(str(_loop4_).split("/")[-1])
                 #      if re.match(str(_loop2_),temp_parse_ipport_info) and (len(str(_loop2_))==len(temp_parse_ipport_info)):
                 #         _temp_traybox_[str(_loop1_[u'device'])][str(_loop2_)].append(str(_loop3_[u'name']))

           for _loop1_ in _user_input_data_nodes_confirm_:
              _temp_dictbox_ = {}
              _mypoolmemberslist_ = _loop1_[u'poolmembers']
              _thisdevice_ = str(_loop1_[u'device'])
              # init box and counting
              for _loop2_ in _mypoolmemberslist_:
                 _inputipport_info_ = str(_loop2_)
                 _searched_poolnamelist_ = _temp_traybox_[_thisdevice_][_inputipport_info_]
                 for _loop3_ in _searched_poolnamelist_:
                    _fromapi_poolname_ = str(_loop3_)
                    if _fromapi_poolname_ not in _temp_dictbox_.keys():
                      _temp_dictbox_[_fromapi_poolname_] = int(1)
                    else:
                      _temp_dictbox_[_fromapi_poolname_] = _temp_dictbox_[_fromapi_poolname_] + int(1)
              # find pool name matched (used poolname will be searched!)
              _temp_listbox_ = [] 
              _temp_dictbox_keyname_ = _temp_dictbox_.keys()
              for _fromapi_poolname_ in _temp_dictbox_keyname_:
                 if int(_temp_dictbox_[_fromapi_poolname_]) == int(len(_mypoolmemberslist_)):
                   if str(_fromapi_poolname_) not in _temp_listbox_:
                     _temp_listbox_.append(str(_fromapi_poolname_))
              _loop1_[u'poolnames_list'] = _temp_listbox_
           
           # this is not necessay, it will be duplicated
           #for _loop1_ in _user_input_data_nodes_confirm_:
           #   _temp_listbox_ = []
           #   for _loop2_ in _loop1_[u'poolnames_list']:
           #      database_filename = USER_DATABASES_DIR+"poollist."+str(_loop1_[u'pairdevice'])+".txt"
           #      f = open(database_filename,"r")
           #      _contents_ = f.readlines()
           #      f.close()
           #      stream = BytesIO(_contents_[0])
           #      data_from_file = JSONParser().parse(stream)
           #      for _loop3_ in data_from_file[u'items']:
           #         if re.search(str(_loop2_),str(_loop3_[u'name'])) and len(_loop1_[u'poolmembers']) == len(_loop3_[u'poolmembers_status_list']):
           #           if str(_loop3_[u'name']) not in _temp_listbox_:
           #             _temp_listbox_.append(str(_loop3_[u'name']))
           #   _loop1_[u'poolnames_list'] = _temp_listbox_


           _valid_user_input_data_ = copy.copy(_user_input_data_nodes_confirm_)


           _return_message_list_ = []
           for _loop1_ in _valid_user_input_data_:

              ## if len(_loop1_[u'virtualserver_names_list']) == int(0):

                 # Parameter re-arrange
                 info_in_pairdevice = _loop1_[u'pairdevice']
                 info_in_poolnames_list = _loop1_[u'poolnames_list']
                 info_in_virtual_ip_port = _loop1_[u'virtual_ip_port']
                 info_in_servername = _loop1_[u'servername']
                 info_in_poolmembers = _loop1_[u'poolmembers']
                 info_in_device = _loop1_[u'device']
                 info_in_syncgroup = _loop1_[u'syncgroup']
                 info_in_portforward_status = _loop1_[u'portforward_status']

                 ### server name recreation
                 SERVERHOST_name = str('_'.join(info_in_servername.strip().split('-')))

                 ### GET CONFIG_OPTION_SETTING_VALUE
                 sticky_from_CONFvalue = ""
                 profile_from_CONFvalue = ""
                 createpoolcmd_from_CONFvalue = ""
                 for _dictvalues_ in CONFIG_OPTION_SETTING_VALUE:
                    _ipaddresslist_ = _dictvalues_['device']
                    if str(info_in_device) in _ipaddresslist_:
                      sticky_from_CONFvalue = _dictvalues_['sticky']
                      profile_from_CONFvalue = _dictvalues_['profiles']
                      createpoolcmd_from_CONFvalue = _dictvalues_['format_to_create_pool']
                      break
 
                 ### option check confirmation
                 ### stikcy option will be defined
                 info_in_sticky = ""
                 if u'options' in _loop1_.keys():
                   # option : sticky
                   if u'sticky' in _loop1_[u'options']:
                     info_in_sticky = sticky_from_CONFvalue 

                 ### performace l4 option will be defined!
                 info_in_profiles = profile_from_CONFvalue
   
                 # find out the command format to create the pool
                 command_format_to_pool = {}
                 command_format_to_pool[u'create'] = createpoolcmd_from_CONFvalue
                 command_format_to_pool[u'delete'] = COMMOM_CMD_FORMAT["delete_pool_command"]

                 #for _loop2_ in CONFIG_OPTION_SETTING_VALUE:
                 #   if str(info_in_device) in _loop2_["device"]:
                 #     command_format_to_pool[u'create'] = _loop2_["created_command"]
                 #     command_format_to_pool[u'delete'] = COMMOM_CMD_FORMAT["delete_pool_command"]
                 #     break

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


                 # 2016.11.17 poolname creation
                 #_poolname_created_ = "p_%(servername)s_%(portname)s" % {"servername":SERVERHOST_name,"portname":_name_with_ports_}
                 #for _pname_ in info_in_poolnames_list:
                 #   if re.search(_poolname_created_,_pname_,re.I) or re.search(_pname_,_poolname_created_,re.I):
                 #      message = "pool name [%(_poolname_created_)s] has been already used over [%(info_in_device)s] device!" % {"_poolname_created_":_poolname_created_,"info_in_device":info_in_device}
                 #      return Response(message, status=status.HTTP_400_BAD_REQUEST)

                 # create virtual server
                 _splited_ip_ = str(_loop1_[u'virtual_ip_port']).strip().split(':')[0]
                 _splited_port_ = str(_loop1_[u'virtual_ip_port']).strip().split(':')[-1]
                 for optlist in VIP_NAME_OPTION:
                    if info_in_device in optlist["device"]:
                      VIRTUALIP_SPLITE_COUNT = int(optlist["VIRTUALIP_SPLITE_COUNT"])
                 _rename_ip_value_ = str('.'.join(str(_splited_ip_).split('.')[int(VIRTUALIP_SPLITE_COUNT):]))


                 # 2016.11.17 poolname creation
                 for optlist in PORT_NAME_OPTION:
                    if info_in_device in optlist["device"]:
                      _poolname_created_ = optlist["name_string"] % {"servername":SERVERHOST_name,"portname":_name_with_ports_,"ipport":_rename_ip_value_} 
                      break
                 for _pname_ in info_in_poolnames_list:
                    if re.search(_poolname_created_,_pname_,re.I) or re.search(_pname_,_poolname_created_,re.I):
                       message = "pool name [%(_poolname_created_)s] has been already used over [%(info_in_device)s] device!" % {"_poolname_created_":_poolname_created_,"info_in_device":info_in_device}
                       return Response(message, status=status.HTTP_400_BAD_REQUEST)


                 #_virtualservername_created_ = "v_%(ipport)s_%(servername)s_%(portname)s" % {"ipport":_rename_ip_value_,"servername":SERVERHOST_name,"portname":_splited_port_}
                 for optlist in VIP_NAME_OPTION:
                    if info_in_device in optlist["device"]:
                      _virtualservername_created_ = optlist["name_string"] % {"ipport":_rename_ip_value_,"servername":SERVERHOST_name,"portname":_splited_port_}
                      break


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
        message = "post algorithm has some problem!"
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

