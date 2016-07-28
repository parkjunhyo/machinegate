from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.renderers import JSONRenderer
from rest_framework.parsers import JSONParser

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils.six import BytesIO

import os,re,copy,json,threading,time
import glob

from f5restapi.setting import LOG_FILE
from f5restapi.setting import USER_DATABASES_DIR 
from f5restapi.setting import USER_NAME,USER_PASSWORD
from f5restapi.setting import ENCAP_PASSWORD
from f5restapi.setting import THREAD_TIMEOUT
from f5restapi.setting import USER_VAR_STATS

class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders its content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)


@api_view(['GET'])
@csrf_exempt
def f5_virtualserverstats(request,virtualservername,format=None):

   # get method
   if request.method == 'GET':
      try:
         matched_filename = str(virtualservername)
         matched_fullpath = USER_VAR_STATS+matched_filename+"*"
         matched_filelist = glob.glob(matched_fullpath)
         return Response(matched_filelist)
      except:
         _status_all_ = {} 
         message = _status_all_
         return Response(message)


      # get the result data and return
      message = _status_all_
      return Response(message)

