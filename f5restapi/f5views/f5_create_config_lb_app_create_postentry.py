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

           for _listvalue_ in _input_[0][u'items']:
              print _listvalue_

           message = "" 
           return Response(message)


      except:
        message = "post algorithm has some problem!"
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

