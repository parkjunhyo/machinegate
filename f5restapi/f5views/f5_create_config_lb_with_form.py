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
["<service/server name>","<real servers ip address>","<virual ip address>","<service port>","<target device>","<sticky port>"],
["GFTCc-11stprapiweb01","172.22.227.194;172.22.227.195;172.22.227.196","172.22.216.65","80;443","KRIS10-PUBS01-5000L4.skplanet.com","80;443"],
["GFTCc-11stpaapiweb01","172.22.227.200;172.22.227.201;172.22.227.202","172.22.216.66","80;443","KRIS10-PUBS01-5000L4.skplanet.com","x"]
]
}]

port_pattern = ["/",":",";","-","_","@","#","\$","%"]
def parsed_using_port(using_port,pattern):
   parsed_port_numberlist = []
   removed_pattern = copy.copy(pattern)
   for _mark_ in pattern:
      removed_pattern.remove(_mark_)
      splited_string_by_mark = using_port.strip().split(_mark_)
      for _splited_string_ in splited_string_by_mark:
         _string_value_ = str(_splited_string_).strip()
         for _remov_mark_ in removed_pattern:
            if re.search(_remov_mark_,_string_value_,re.I):
              parsed_using_port(_string_value_,removed_pattern)
         if _string_value_ not in parsed_port_numberlist:
           parsed_port_numberlist.append(_string_value_)
   return parsed_port_numberlist 

def remove_pattern_items(parsed_port_numberlist):
   removed_string = []
   for _string_ in parsed_port_numberlist:
      match_status = False
      for _mark_ in port_pattern:
         if re.search(_mark_,_string_,re.I):
           match_status = True
           break
      if not match_status:
        if _string_ not in removed_string:
          removed_string.append(_string_)
   return removed_string


   

@api_view(['GET','POST'])
@csrf_exempt
def f5_create_config_lb_with_form(request,format=None):

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


           item_listdata = _input_[0]['items']
           ipport_pattern_string = "%(ip)s:%(port)s"
           created_items_list = []
           for _param_list_ in item_listdata:

              box_dict = {}             
              service_name = str(_param_list_[0].strip())
              box_dict["servername"] = service_name
              device_name = str(_param_list_[4].strip())
              box_dict["device"] = device_name 
              re_arranged_parsed_sticky_option = remove_pattern_items(parsed_using_port(str(_param_list_[5].strip()),port_pattern))

              realservers_iplist = _param_list_[1]
              re_arranged_parsed_realservers_ip_address = remove_pattern_items(parsed_using_port(_param_list_[1],port_pattern))
              re_arranged_parsed_virtualserver_ip_address = remove_pattern_items(parsed_using_port(_param_list_[2],port_pattern)) 
              if len(re_arranged_parsed_virtualserver_ip_address) != 1:
                message = "virtual ip address %(vipstring)s are wrong!" % {"vipstring":str(";".join(re_arranged_parsed_virtualserver_ip_address))}
                return Response(message, status=status.HTTP_400_BAD_REQUEST)
              using_port = _param_list_[3].strip()
              re_arranged_parsed_port_number = remove_pattern_items(parsed_using_port(using_port,port_pattern))
              for _port_number_ in re_arranged_parsed_port_number:
                 # real ip:port lists
                 realipport_list = []
                 for _ipaddress_ in re_arranged_parsed_realservers_ip_address:
                    _ipport_string_ = ipport_pattern_string % {"ip":str(_ipaddress_),"port":str(_port_number_)}                   
                    if _ipport_string_ not in realipport_list:
                      realipport_list.append(_ipport_string_)
                 box_dict["poolmembers"] = realipport_list 
                 # virtual ip:port lists
                 vipport_name = ipport_pattern_string % {"ip":str(re_arranged_parsed_virtualserver_ip_address[-1]),"port":str(_port_number_)}
                 box_dict["virtual_ip_port"] = vipport_name 
                 # sticky option
                 if (_port_number_ in re_arranged_parsed_sticky_option) or (unicode(_port_number_) in re_arranged_parsed_sticky_option):
                   box_dict["options"] = ["sticky"]

                 # run curl command to get the create command
                 sending_curlmsg = [{}]
                 sending_curlmsg[0]["auth_key"] = ENCAP_PASSWORD
                 sending_curlmsg[0]["items"] = [box_dict]

                 CURL_command = "curl -H \"Accept: application/json\" -X POST -d \'"+json.dumps(sending_curlmsg)+"\' http://0.0.0.0:"+RUNSERVER_PORT+"/f5/create/config/lb/"
                 get_info = os.popen(CURL_command).read().strip()
                 stream = BytesIO(get_info)
                 data_from_CURL_command = JSONParser().parse(stream)

                 # make list to command cli
                 if type(data_from_CURL_command) == list:
                   created_items_list.append(data_from_CURL_command[0])
                 elif type(data_from_CURL_command) == unicode:
                   created_items_list.append(data_from_CURL_command)
                
           return Response(created_items_list)



      except:
        message = "post algorithm has some problem!"
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

