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
from f5restapi.setting import STATS_SAVEDDATA_MULTI
from f5restapi.setting import ROLLBAK_INTERVAL

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
def f5_virtualserverstats_by_rollback(request,virtualservername,rollback_interval,format=None):

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

            ## added 0909 to extract rollback parameter
            floatbox = float(0)
            sorting_dict_container = {}
            _copied_contents_ = copy.copy(_contents_)
            for _copied_contents_item_ in _copied_contents_:
               IOString = _copied_contents_item_.strip()
               stream = BytesIO(IOString)
               json_stream = JSONParser().parse(stream)
               if (matched_filename not in json_stream.keys()) or (unicode(matched_filename) not in json_stream.keys()):
                 return Response("database is not matched with the server name!")
               floatbox = float(json_stream[unicode(matched_filename)][u'updated_time'])
               sorting_dict_container[floatbox] = json_stream[unicode(matched_filename)]
  
            unicode_timevalue_list = sorting_dict_container.keys()
            unicode_timevalue_list.sort()
            last_time = unicode_timevalue_list[-1]

            # start end time value calculation
            before_time = int(rollback_interval)
            backtotime_interval = float(int(ROLLBAK_INTERVAL)*int(before_time))
            if float(last_time) < float(backtotime_interval):
              predicted_past_time = float(last_time)
            else:
              predicted_past_time = float(last_time)-float(backtotime_interval)
 
            findabs_box = {}
            for _univalue_ in unicode_timevalue_list:
               abs_interval_value = abs(float(_univalue_)-float(predicted_past_time))
               findabs_box[abs_interval_value] = _univalue_
            findabs_box_keys = findabs_box.keys()
            findabs_box_keys.sort()
            matched_final_time = findabs_box[findabs_box_keys[0]]

            # 
            matched_index = unicode_timevalue_list.index(matched_final_time)
            included_matched_index = matched_index + int(1)
          
            valid_timevalue = []
            if matched_index <= STATS_VIEWER_COUNT:
              valid_timevalue = unicode_timevalue_list[:included_matched_index]
            else:
              start_index = int(matched_index - STATS_VIEWER_COUNT)
              valid_timevalue = unicode_timevalue_list[start_index:included_matched_index]

            ordered_list = []
            for _time_item_ in valid_timevalue:
               temp_dictbox = {}
               temp_dictbox[unicode(matched_filename)] = {}
               temp_dictbox[unicode(matched_filename)] = sorting_dict_container[_time_item_]
               ordered_list.append(temp_dictbox)


            for datafrom_filestring in ordered_list:
               if len(datafrom_filestring.keys()) != 1 or not re.search(matched_filename,str(datafrom_filestring.keys())):
                 continue
               dictkey_datafrom_filestring = datafrom_filestring.keys()
               items_keyname_dict = datafrom_filestring[dictkey_datafrom_filestring[0]].keys()
               if ((u'updated_time') not in items_keyname_dict):
                 continue
               float_id = float(datafrom_filestring[dictkey_datafrom_filestring[0]][u'updated_time'])
               stats_inform_dict[unicode(parsed_filename)][float_id] = {}
               stats_inform_dict[unicode(parsed_filename)][float_id] = datafrom_filestring[dictkey_datafrom_filestring[0]]

            all_stats_list.append(stats_inform_dict)

            ## if len(_contents_) <= (int(STATS_VIEWER_COUNT)*int(STATS_SAVEDDATA_MULTI)):
            #if len(_contents_) <= int(STATS_VIEWER_COUNT):
            #  possible_contents = _contents_
            #else:        
            #  # possible_numbering = int(len(_contents_) - (int(STATS_VIEWER_COUNT)*int(STATS_SAVEDDATA_MULTI)))
            #  possible_numbering = int(len(_contents_) - int(STATS_VIEWER_COUNT))
            #  possible_contents = _contents_[possible_numbering:]

            #for _read_content_ in possible_contents:
            #   stream = BytesIO(_read_content_)
            #   datafrom_filestring = JSONParser().parse(stream)

            #   if len(datafrom_filestring.keys()) != 1 or not re.search(matched_filename,str(datafrom_filestring.keys())):
            #     continue
            #   dictkey_datafrom_filestring = datafrom_filestring.keys()

            #   items_keyname_dict = datafrom_filestring[dictkey_datafrom_filestring[0]].keys()
            #   if ((u'updated_time') not in items_keyname_dict):
            #     continue
            
            #   float_id = float(datafrom_filestring[dictkey_datafrom_filestring[0]][u'updated_time'])
            #   stats_inform_dict[unicode(parsed_filename)][float_id] = {}
            #   stats_inform_dict[unicode(parsed_filename)][float_id] = datafrom_filestring[dictkey_datafrom_filestring[0]]

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
            #all_stats_list.append(stats_inform_dict)

         return Response(all_stats_list)

      except:
         return Response("stats data is not normal!")


      # get the result data and return
      message = _status_all_
      return Response(message)
