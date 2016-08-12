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




getview_message = [{
                     "items":[
                               ["<server name>","<server/host real ip address>","<virtual server bind ip address>","<service ports>","<target device name>","<sticky enable>"],
                               ["ANNEc-admin02","172.22.164.57","172.22.160.9","80/443","KRIS10-PUBS01-5000L4","O"]
                             ]
                  }]

PORT_SPLIT_STRING = ["@","/",";",":","_","\\","~","-"]

def parse_str_by_number(string_msg):
   msg_pattern = r"([a-zA-Z_\-]*)([0-9]*[a-zA-Z_\-]*([0-9]*))([a-zA-Z_\-]*)"
   match = re.match(msg_pattern,string_msg.strip(),re.I)
   match_return = None
   if match:
     match_tuple = match.groups()
     match_return = match_tuple[0]
   return match_return

def parse_port_by_mark(string_msg):
   recursive_list = [string_msg]
   for _mark_ in PORT_SPLIT_STRING:
      sum_list = []
      for _port_string_ in recursive_list:
         splited_list = _port_string_.strip().split(_mark_)
         for _splited_ in splited_list:
            if _splited_ not in sum_list:
              sum_list.extend(splited_list)
      recursive_list = sum_list
   return recursive_list





@api_view(['GET','POST'])
@csrf_exempt
def f5_create_config_lb_app_create_postentry(request,format=None):

   # get method
   if request.method == 'GET':
      return Response(getview_message)

   elif request.method == 'POST':

      try:

        _input_ = JSONParser().parse(request)

        if u'auth_key' not in _input_[0].keys():
           message = "you do not have permission to use this service!"
           return Response(message, status=status.HTTP_400_BAD_REQUEST)

        input_encap_password = str(_input_[0][u'auth_key'])
        if re.match(input_encap_password,ENCAP_PASSWORD):

           # items 
           thisitems_list = _input_[0][u'items']

           # this part create the container box to store the device name data
           devicenames_list = []
           inform_container = {}
           for _listvalue_ in thisitems_list:
              org_devicename_string = str(_listvalue_[4])
              if org_devicename_string not in devicenames_list:
                devicenames_list.append(org_devicename_string)
                inform_container[unicode(org_devicename_string)] = {}


           inform_container_keyname = inform_container.keys()
           for _keyname_ in inform_container_keyname:

              # this part find out the host and server name by the device
              hostservername_list = []
              for _listvalue_ in thisitems_list:
                 org_servername_string = str(_listvalue_[0])
                 org_devicename_string = str(_listvalue_[4])
                 parsed_present_servername_string = parse_str_by_number(org_servername_string)
                 if not parsed_present_servername_string:
                   message = "server name [%(org_servername_string)s] is not proper!" % {"org_servername_string":org_servername_string}
                   return Response(message, status=status.HTTP_400_BAD_REQUEST)
                 if re.match(str(_keyname_),org_devicename_string,re.I) and (parsed_present_servername_string not in hostservername_list):
                   hostservername_list.append(parsed_present_servername_string)

              # using the host server name 
              for _str_value_ in hostservername_list:

                 present_hostname = str(_str_value_)
                 # container init
                 if unicode(present_hostname) not in inform_container[unicode(_keyname_)].keys():
                   inform_container[unicode(_keyname_)][unicode(present_hostname)] = {}

                 thishost_use_port_list = []
                 thishost_use_realserver_list = []
                 thishost_use_virtualserver_list = []
                 thishost_use_sticky = []
                 for _listvalue_ in thisitems_list:
                    org_servername_string = str(_listvalue_[0])
                    org_devicename_string = str(_listvalue_[4])
                    if re.search(present_hostname,org_servername_string,re.I) and re.match(str(_keyname_),org_devicename_string,re.I):
                      # port 
                      org_port_string = str(_listvalue_[3])
                      org_port_list = parse_port_by_mark(org_port_string)
                      if len(org_port_list) != 0:
                        for _port_ in org_port_list:
                           if _port_ not in thishost_use_port_list:
                             thishost_use_port_list.append(_port_)
                      # real server ip
                      org_realserverip_string = str(_listvalue_[1])
                      if org_realserverip_string not in thishost_use_realserver_list:
                        thishost_use_realserver_list.append(org_realserverip_string)
                      # virtual server ip
                      org_virtualserverip_string = str(_listvalue_[2])
                      if org_virtualserverip_string not in thishost_use_virtualserver_list:
                        thishost_use_virtualserver_list.append(org_virtualserverip_string)
                      # sticky
                      org_sticky_string = str(_listvalue_[5])
                      if org_sticky_string not in thishost_use_sticky:
                        if re.match('o',org_sticky_string,re.I):
                          thishost_use_sticky.append(org_sticky_string) 

                 for _port_ in thishost_use_port_list:
                    _ripport_list_ = []
                    for _rip_ in thishost_use_realserver_list:
                       ripport_string = str("%(_rip_)s:%(_port_)s" % {"_rip_":_rip_,"_port_":_port_})
                       if ripport_string not in _ripport_list_:
                         _ripport_list_.append(ripport_string)

                    for _vip_ in thishost_use_virtualserver_list:
                       vipport_string = str("%(_vip_)s:%(_port_)s" % {"_vip_":_vip_,"_port_":_port_})
                       if unicode(vipport_string) not in inform_container[unicode(_keyname_)][unicode(present_hostname)].keys():
                         inform_container[unicode(_keyname_)][unicode(present_hostname)][unicode(vipport_string)] = {}
                         inform_container[unicode(_keyname_)][unicode(present_hostname)][unicode(vipport_string)][unicode("items")] = _ripport_list_
                         sticky_status = "disable"
                         if len(thishost_use_sticky) != 0:
                           sticky_status = "enable"
                         inform_container[unicode(_keyname_)][unicode(present_hostname)][unicode(vipport_string)][unicode("sticky")] = sticky_status


           # the format is creating using the informations
           inform_container_keyname = inform_container.keys()
           itemsbox = []
           for _devicename_ in inform_container_keyname:
              _devicename_string_ = str(_devicename_)
              for _hostname_ in inform_container[unicode(_devicename_)].keys():
                 _hostname_string_ = str(_hostname_)
                 _hostservername_ = str("_".join(_hostname_string_.strip().split("-")))

                 for _virtualipport_ in inform_container[unicode(_devicename_)][unicode(_hostname_string_)].keys():
                    _virtualipport_string_ = str(_virtualipport_)
                    _realipport_list_ = inform_container[unicode(_devicename_)][unicode(_hostname_string_)][unicode(_virtualipport_string_)][unicode("items")]
                    format_item = {
                                      "virtual_ip_port":_virtualipport_string_,
                                      "device":_devicename_string_,
                                      "servername":_hostservername_,
                                      "poolmembers":_realipport_list_
                                  }
                    matching_string = inform_container[unicode(_devicename_)][unicode(_hostname_string_)][unicode(_virtualipport_string_)][unicode("sticky")]
                    if re.match(str("enable"),matching_string,re.I):
                      format_item["options"] = [str("sticky")]
                    itemsbox.append(format_item)

           return Response(itemsbox)


      except:
        message = "post algorithm has some problem!"
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

