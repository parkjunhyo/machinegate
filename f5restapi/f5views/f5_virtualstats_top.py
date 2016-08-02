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
from f5restapi.setting import STATS_TOP_COUNT
from f5restapi.setting import RUNSERVER_PORT

class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders its content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)


def get_active_devices_list():
   # find out the active device 
   f = open(USER_DATABASES_DIR + "devicelist.txt",'r')
   _string_contents_ = f.readlines()
   f.close()
   stream = BytesIO(_string_contents_[0])
   _data_from_devicelist_db_= JSONParser().parse(stream)
   # active server list
   active_device_list = []
   for _dict_information_ in _data_from_devicelist_db_:
      if re.match('active',str(_dict_information_[u'failover'])):
         if str(_dict_information_[u'devicehostname']) not in active_device_list:
            active_device_list.append(str(_dict_information_[u'devicehostname']))
   # return
   return active_device_list 
    
def get_stats_information(category_value,active_device_list):
    rank_dict_data = {} 
    for _active_device_ in active_device_list:
       stats_filename = "*@*"+_active_device_+".virtual.stats"
       matched_filelist = glob.glob(USER_VAR_STATS+stats_filename)
       rank_dict_data[unicode(_active_device_)] = {}

       compare_container = {}
       for _mfilename_ in matched_filelist:
          f = open(_mfilename_,'r')
          _read_contents_ = f.readlines()
          f.close()
          _last_string_ = _read_contents_[-1].strip()
          stream = BytesIO(_last_string_)
          _dictdata_ = JSONParser().parse(stream)

          if len(_dictdata_.keys()) != 1:
            continue

          _keyname_ = _dictdata_.keys()[-1].strip()
          _interval_ = _dictdata_[_keyname_][unicode("interval")]
          _matched_inner_keyname_ = []
          for _inner_keyname_ in _dictdata_[unicode(_keyname_)].keys():
             _value_ = str(_inner_keyname_.lower())
             if re.search(category_value,_value_):
               _matched_inner_keyname_.append(_inner_keyname_)

          if len(_matched_inner_keyname_) == 0:
             continue

          for _inner_keyname_ in _matched_inner_keyname_:
             if unicode(_inner_keyname_) not in compare_container.keys():
                compare_container[unicode(_inner_keyname_)] = {}

          for _inner_keyname_ in _matched_inner_keyname_:
             _float_id_ = float(_dictdata_[unicode(_keyname_)][unicode(_inner_keyname_)])


             if _float_id_ not in compare_container[unicode(_inner_keyname_)].keys():
               compare_container[unicode(_inner_keyname_)][_float_id_] = []
               _fname_ = str(_mfilename_.strip().split("/")[-1]).split("@")[0]
               compare_container[unicode(_inner_keyname_)][_float_id_].append(_fname_)
             else:
               _fname_ = str(_mfilename_.strip().split("/")[-1])
               _fname_ = str(_mfilename_.strip().split("/")[-1]).split("@")[0]
               compare_container[unicode(_inner_keyname_)][_float_id_].append(_fname_)

       _container_keyname_ = compare_container.keys()
       sorted_container = {}
       for _keyname_ in _container_keyname_:

          rank_dict_data[unicode(_active_device_)][unicode(_keyname_)] = {}
          sorted_container = {}
          sorted_id = compare_container[_keyname_].keys()
          sorted_id.sort()
          total_count = int(len(sorted_id))
          if total_count < STATS_TOP_COUNT:
            selected_values = sorted_id
          else:
            selected_values = sorted_id[int(total_count)-int(STATS_TOP_COUNT):]
          selected_values.reverse()

          rank = int(0)
          for _sorted_values_ in selected_values:
             sorted_container[rank] = {}
             sorted_container[rank][unicode(str("virtualservers"))] = compare_container[_keyname_][_sorted_values_]
             sorted_container[rank][unicode(str("value"))] = _sorted_values_
             rank = rank + int(1)

          rank_dict_data[unicode(_active_device_)][unicode(_keyname_)] = sorted_container

    return rank_dict_data


@api_view(['GET','POST'])
@csrf_exempt
def f5_virtualstats_top(request,key_value,format=None):

   # get method
   if request.method == 'GET':
      try:

         # send curl command to device for virtual serverlist update
         #CURL_command = "curl -H \"Accept: application/json\" -X POST -d \'[{\"auth_key\":\""+ENCAP_PASSWORD+"\"}]\' http://0.0.0.0:"+RUNSERVER_PORT+"/f5/stats/virtual/"
         #get_info = os.popen(CURL_command).read().strip()

         category_value = str(key_value).lower()

         # find out the active device 
         active_device_list = get_active_devices_list()
        
         rank_dict_data = get_stats_information(category_value,active_device_list)

         #rank_dict_data = {} 
         #for _active_device_ in active_device_list:
         #   stats_filename = "*@*"+_active_device_+".virtual.stats"
         #   matched_filelist = glob.glob(USER_VAR_STATS+stats_filename)
         #   rank_dict_data[unicode(_active_device_)] = {}


         #   compare_container = {} 
         #   for _mfilename_ in matched_filelist:
         #      f = open(_mfilename_,'r')
         #      _read_contents_ = f.readlines()
         #      f.close()
         #      _last_string_ = _read_contents_[-1].strip()
         #      stream = BytesIO(_last_string_)
         #      _dictdata_ = JSONParser().parse(stream)
 
         #      if len(_dictdata_.keys()) != 1:
         #        continue

         #      _keyname_ = _dictdata_.keys()[-1].strip()
         #      _interval_ = _dictdata_[_keyname_][unicode("interval")]
         #      _matched_inner_keyname_ = [] 
         #      for _inner_keyname_ in _dictdata_[unicode(_keyname_)].keys():
         #         _value_ = str(_inner_keyname_.lower())
         #         if re.search(category_value,_value_):
         #           _matched_inner_keyname_.append(_inner_keyname_)

         #      if len(_matched_inner_keyname_) == 0:
         #         continue

         #      for _inner_keyname_ in _matched_inner_keyname_:
         #         if unicode(_inner_keyname_) not in compare_container.keys():
         #            compare_container[unicode(_inner_keyname_)] = {}

         #      for _inner_keyname_ in _matched_inner_keyname_:
         #         _float_id_ = float(_dictdata_[unicode(_keyname_)][unicode(_inner_keyname_)]) 
                  

         #         if _float_id_ not in compare_container[unicode(_inner_keyname_)].keys():
         #           compare_container[unicode(_inner_keyname_)][_float_id_] = []
         #           _fname_ = str(_mfilename_.strip().split("/")[-1]).split("@")[0]
         #           compare_container[unicode(_inner_keyname_)][_float_id_].append(_fname_)
         #         else:
         #           _fname_ = str(_mfilename_.strip().split("/")[-1])
         #           _fname_ = str(_mfilename_.strip().split("/")[-1]).split("@")[0]
         #           compare_container[unicode(_inner_keyname_)][_float_id_].append(_fname_)

         #   _container_keyname_ = compare_container.keys() 
         #   sorted_container = {}
         #   for _keyname_ in _container_keyname_:

         #      rank_dict_data[unicode(_active_device_)][unicode(_keyname_)] = {}
         #      sorted_container = {}
         #      sorted_id = compare_container[_keyname_].keys()
         #      sorted_id.sort()
         #      total_count = int(len(sorted_id)) 
         #      if total_count < STATS_TOP_COUNT:
         #        selected_values = sorted_id 
         #      else:
         #        selected_values = sorted_id[int(total_count)-int(STATS_TOP_COUNT):]
         #      selected_values.reverse()

         #      rank = int(0)
         #      for _sorted_values_ in selected_values:
         #         sorted_container[rank] = {}
         #         sorted_container[rank][unicode(str("virtualservers"))] = compare_container[_keyname_][_sorted_values_]
         #         sorted_container[rank][unicode(str("value"))] = _sorted_values_
         #         #sorted_container[rank] = compare_container[_keyname_][_sorted_values_]
         #         rank = rank + int(1)

         #      rank_dict_data[unicode(_active_device_)][unicode(_keyname_)] = sorted_container 
         

         return Response(rank_dict_data)
      except:
         return Response("stats data is not normal!",status=status.HTTP_400_BAD_REQUEST)


   elif request.method == 'POST':
      try:
        _input_ = JSONParser().parse(request)
        message = ""
        if re.match(ENCAP_PASSWORD,str(_input_[0]['auth_key'])):
          # send curl command to device for virtual serverlist update
          CURL_command = "curl -H \"Accept: application/json\" -X POST -d \'[{\"auth_key\":\""+ENCAP_PASSWORD+"\"}]\' http://0.0.0.0:"+RUNSERVER_PORT+"/f5/stats/virtual/"
          get_info = os.popen(CURL_command).read().strip()
          category_value = str(key_value).lower()
          active_device_list = get_active_devices_list()
          rank_dict_data = get_stats_information(category_value,active_device_list)
        return Response(rank_dict_data)
      except:
        return Response("stats data is not normal!",status=status.HTTP_400_BAD_REQUEST)
       
