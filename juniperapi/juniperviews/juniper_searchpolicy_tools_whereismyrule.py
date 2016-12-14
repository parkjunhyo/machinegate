from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.renderers import JSONRenderer
from rest_framework.parsers import JSONParser

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils.six import BytesIO

from juniperapi.setting import USER_DATABASES_DIR
from juniperapi.setting import USER_NAME
from juniperapi.setting import USER_PASSWORD
from juniperapi.setting import ENCAP_PASSWORD
from juniperapi.setting import RUNSERVER_PORT
from juniperapi.setting import PARAMIKO_DEFAULT_TIMEWAIT
from juniperapi.setting import USER_VAR_POLICIES 

import os,re,copy,json,time,threading,sys,random
import paramiko
from netaddr import *

# thread parameter (added)
global tatalsearched_values, threadlock_key

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
def juniper_searchpolicy_tools_whereismyrule(request,format=None):

   # thread parameter initailization
   global tatalsearched_values, threadlock_key
   tatalsearched_values = []
   threadlock_key = threading.Lock()

   # get method
   if request.method == 'GET':
      try:
         get_message = [
           {
             "sourceip" : "172.22.113.10/32;172.22.113.11/32",
             "destinationip" : "172.22.208.15/32",
             "application" : "tcp/0-0:1700-1700;<protocol>/<souce port range>:<destination port range>"
           },
           {
             "sourceip" : "172.22.0.0/16",
             "destinationip" : "172.22.209.0/24",
             "application" : "icmp/0-0:0-65535"
           },
           {
             "sourceip" : "172.22.112.0/23",
             "destinationip" : "172.22.208.10/28",
             "application" : "any/0-0:0-0;tcp/0-0:0-0;udp/0-65535:0-65535"
           }
         ]
         return Response(get_message)
      except:
         message = ["device list database is not existed!"]
         return Response(message, status=status.HTTP_400_BAD_REQUEST)


   elif request.method == 'POST':

      try:

        # input
        _input_ = JSONParser().parse(request)

        # cache directory
        policies_filename = os.listdir(USER_VAR_POLICIES)

        # get the matched and searched policy
        CURL_command = "curl -H \"Accept: application/json\" -X POST -d \'"+json.dumps(_input_)+"\' http://0.0.0.0:"+RUNSERVER_PORT+"/juniper/searchpolicy/"
        get_info = os.popen(CURL_command).read().strip()
        stream = BytesIO(get_info)
        data_from_CURL_command = JSONParser().parse(stream)

        ## thread parameter
        #_threads_ = []
        #for _dictData_ in data_from_CURL_command:
        #   th = threading.Thread(target=searching_matchingpolicy_from_request, args=(_dictData_,_routing_dict_,cache_filename,))
        #   th.start()
        #   _threads_.append(th)
        #for th in _threads_:
        #   th.join()
   
        # thread finish : read and transfer global value 
        return Response(data_from_CURL_command)

      except:
        message = "Post Algorithm has some problem!"
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

