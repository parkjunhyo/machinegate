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
from f5restapi.setting import STATS_VIEWER_COUNT

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
         matched_fullpath = USER_VAR_STATS+matched_filename+"*.virtual.stats"
         matched_filelist = glob.glob(matched_fullpath)

         all_stats_list = []
         for _filename_ in matched_filelist:
            stats_inform_dict = {} 

            parsed_filename = str(str(_filename_).strip().split("/")[-1])
            stats_inform_dict[unicode(parsed_filename)] = {}

            id_count = int(0)
            f = open(_filename_,'r')
            _contents_ = f.readlines()
            f.close()

            if len(_contents_) <= int(STATS_VIEWER_COUNT):
              possible_contents = _contents_
            else:
              possible_numbering = int(len(_contents_) - int(STATS_VIEWER_COUNT))
              possible_contents = _contents_[possible_numbering:]

            for _read_content_ in possible_contents:
               stream = BytesIO(_read_content_)
               datafrom_filestring = JSONParser().parse(stream)

               if len(datafrom_filestring.keys()) != 1 or not re.search(matched_filename,str(datafrom_filestring.keys())):
                 continue
               dictkey_datafrom_filestring = datafrom_filestring.keys()

               items_keyname_dict = datafrom_filestring[dictkey_datafrom_filestring[0]].keys()
               if ((u'updated_time') not in items_keyname_dict):
                 continue
            
               float_id = float(datafrom_filestring[dictkey_datafrom_filestring[0]][u'updated_time'])
               stats_inform_dict[unicode(parsed_filename)][float_id] = {}
               stats_inform_dict[unicode(parsed_filename)][float_id] = datafrom_filestring[dictkey_datafrom_filestring[0]]

            #while True:
            #  _read_content_ = f.readline().strip()
            #  if not _read_content_:
            #    break
            #  stats_inform_dict[unicode(parsed_filename)][id_count] = {}

            #  stream = BytesIO(_read_content_) 
            #  datafrom_filestring = JSONParser().parse(stream)
            #  if len(datafrom_filestring.keys()) != 1:
            #    continue
            #  dictkey_datafrom_filestring = datafrom_filestring.keys()

            #  stats_inform_dict[unicode(parsed_filename)][id_count] = datafrom_filestring[dictkey_datafrom_filestring[0]]
            #  id_count = id_count + int(1)
            #f.close()
            all_stats_list.append(stats_inform_dict)

         return Response(all_stats_list)

      except:
         return Response("stats data is not normal!")


      # get the result data and return
      message = _status_all_
      return Response(message)
