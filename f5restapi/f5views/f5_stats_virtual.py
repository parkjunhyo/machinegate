from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.renderers import JSONRenderer
from rest_framework.parsers import JSONParser

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils.six import BytesIO

import os,re,copy,json,threading,time,sys
import os.path,glob

from f5restapi.setting import LOG_FILE
from f5restapi.setting import USER_DATABASES_DIR 
from f5restapi.setting import USER_NAME,USER_PASSWORD
from f5restapi.setting import ENCAP_PASSWORD
from f5restapi.setting import THREAD_TIMEOUT
from f5restapi.setting import RUNSERVER_PORT
from f5restapi.setting import USER_VAR_STATS
from f5restapi.setting import STATS_VIEWER_COUNT
from f5restapi.setting import STATS_SAVEDDATA_MULTI

class Param_container():
   active_devices_list = []
   active_devices_dict = {}
   standby_devices_list = []
   standby_devices_dict = {}

   time_parsed_ctime = "string"
   time_time = float(0)


class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders its content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)

def calculation_gap(_from_,_to_):
   _float_from_ = float(_from_)
   _float_to_ = float(_to_)
   if _float_to_ < _float_from_:
     raise Exception
   return abs(float(_float_to_ - _float_from_))

def parsing_from_items_with_keyname(_keyname_,_origin_items_,_updated_items_,time_gab,interval_string,end_time_time):
   virservername_keyname = str(_updated_items_[_keyname_][u'nestedStats'][u'entries'][u'tmName'][u'description']).strip().split("/")[-1]
   # init output values
   output_values = {}
   output_values[unicode(str(virservername_keyname))] = {}
  
   # bps in
   if _keyname_ not in _origin_items_.keys():
      start_value = float(0)
   else:
      start_value = float(_origin_items_[_keyname_][u'nestedStats'][u'entries'][u'clientside.bitsIn'][u'value'])
   end_value = float(_updated_items_[_keyname_][u'nestedStats'][u'entries'][u'clientside.bitsIn'][u'value'])
   output_values[unicode(str(virservername_keyname))][u'bpsIn'] = float(calculation_gap(start_value,end_value)/time_gab)

   # bps out
   if _keyname_ not in _origin_items_.keys():
      start_value = float(0)
   else:
      start_value = float(_origin_items_[_keyname_][u'nestedStats'][u'entries'][u'clientside.bitsOut'][u'value'])
   end_value = float(_updated_items_[_keyname_][u'nestedStats'][u'entries'][u'clientside.bitsOut'][u'value'])
   output_values[unicode(str(virservername_keyname))][unicode('bpsOut')] = float(calculation_gap(start_value,end_value)/time_gab)

   # pps in
   if _keyname_ not in _origin_items_.keys():
      start_value = float(0)
   else:
      start_value = float(_origin_items_[_keyname_][u'nestedStats'][u'entries'][u'clientside.pktsIn'][u'value'])
   end_value = float(_updated_items_[_keyname_][u'nestedStats'][u'entries'][u'clientside.pktsIn'][u'value'])
   output_values[unicode(str(virservername_keyname))][unicode('ppsIn')] = float(calculation_gap(start_value,end_value)/time_gab)

   # pps out
   if _keyname_ not in _origin_items_.keys():
      start_value = float(0)
   else:
      start_value = float(_origin_items_[_keyname_][u'nestedStats'][u'entries'][u'clientside.pktsOut'][u'value'])
   end_value = float(_updated_items_[_keyname_][u'nestedStats'][u'entries'][u'clientside.pktsOut'][u'value'])
   output_values[unicode(str(virservername_keyname))][unicode('ppsOut')] = float(calculation_gap(start_value,end_value)/time_gab)

   # cps
   if _keyname_ not in _origin_items_.keys():
      start_value = float(0)
   else:
      start_value = float(_origin_items_[_keyname_][u'nestedStats'][u'entries'][u'clientside.totConns'][u'value'])
   end_value = float(_updated_items_[_keyname_][u'nestedStats'][u'entries'][u'clientside.totConns'][u'value'])
   output_values[unicode(str(virservername_keyname))][unicode('cps')] = float(calculation_gap(start_value,end_value)/time_gab)

   # current session
   output_values[unicode(str(virservername_keyname))][unicode('session')] = float(_updated_items_[_keyname_][u'nestedStats'][u'entries'][u'clientside.curConns'][u'value'])

   # interval
   output_values[unicode(str(virservername_keyname))][unicode('interval')] = interval_string
   output_values[unicode(str(virservername_keyname))][unicode('updated_time')] = end_time_time

   return output_values

def get_viewer():
    try:
       # read db file
       _devicelist_db_ = USER_DATABASES_DIR + "devicelist.txt"
       f = open(_devicelist_db_,'r')
       _string_contents_ = f.readlines()
       f.close()
       stream = BytesIO(_string_contents_[0])
       _data_from_devicelist_db_= JSONParser().parse(stream)

       # active server list
       active_device_list = []
       for _dict_information_ in _data_from_devicelist_db_:
          if re.match('active',str(_dict_information_[u'failover'])):
            if str(_dict_information_[u'ip']) not in Param_container.active_devices_list:
               Param_container.active_devices_list.append(str(_dict_information_[u'ip']).strip())
               Param_container.active_devices_dict[unicode(str(_dict_information_[u'ip']).strip())] = str(_dict_information_[u'devicehostname']).strip()

       # active server list
       _result_ = {}
       for active_device_ip in Param_container.active_devices_list:

          uncode_active_device_ip = unicode(str(active_device_ip).strip())
          _stats_db_ = USER_DATABASES_DIR + "stats.virtualserver."+str(active_device_ip)+".txt"
          # file check, file is not exist, pass through
          if not os.path.isfile(_stats_db_):
            continue

          f = open(_stats_db_,'r')
          _string_contents_ = f.readlines()
          f.close()
         
          if not len(_string_contents_):
            continue
         
          stream = BytesIO(_string_contents_[0])
          _data_from_file_= JSONParser().parse(stream)

          if (u'origin_ctime' not in _data_from_file_.keys()) or (u'origin_time' not in _data_from_file_.keys()):
            continue
          if (u'updated_ctime' not in _data_from_file_.keys()) or (u'updated_time' not in _data_from_file_.keys()):
            continue
            
          # get the time data to display
          start_current_time = str(_data_from_file_[u'origin_ctime'])
          end_current_time = str(_data_from_file_[u'updated_ctime'])

          start_time_time = float(_data_from_file_[u'origin_time'])
          end_time_time = float(_data_from_file_[u'updated_time'])

          # confirm the date varidation, time must be bigger
          if float(end_time_time - start_time_time) <= float(0):
            continue
          time_gab = abs(float(end_time_time - start_time_time))
          interval_string = start_current_time+"~"+end_current_time+"("+str(time_gab)+")"

          # inti the variable and make container to put in 
          origin_inform = _data_from_file_[u'origin_items']
          updated_inform = _data_from_file_[u'updated_items']
          origin_inform_keys = origin_inform.keys()
          updated_inform_keys = updated_inform.keys()
          _result_[uncode_active_device_ip] = {}

          for _loop2_ in updated_inform_keys:

             virservername_keyname = str(updated_inform[_loop2_][u'nestedStats'][u'entries'][u'tmName'][u'description']).strip().split("/")[-1]
             _this_value_ = parsing_from_items_with_keyname(_loop2_,origin_inform,updated_inform,time_gab,interval_string,end_time_time)
             _result_[uncode_active_device_ip].update(_this_value_)

       if len(_result_.keys()) == 0:
         _result_ = "data is not enough, need to update!"
             
    except:
       # except
       message = "there is errors, need to be update."
       return Response(message, status=status.HTTP_400_BAD_REQUEST)

    return _result_ 

def get_virtual_status_info():

    try:

       filelist_in_var_stats = glob.glob(USER_VAR_STATS+"*.virtual.stats")
       filelist_updated = []
       _result_ = {}


       for _loop1_ in Param_container.active_devices_list:

          active_device_ip = str(_loop1_)
          uncode_active_device_ip = unicode(str(active_device_ip).strip())
          _stats_db_ = USER_DATABASES_DIR + "stats.virtualserver."+str(active_device_ip)+".txt"

          # file check, file is not exist, pass through
          if not os.path.isfile(_stats_db_):
            continue

          f = open(_stats_db_,'r')
          _string_contents_ = f.readlines()
          f.close()
          stream = BytesIO(_string_contents_[0])
            
          if not len(_string_contents_):
            continue
            
          _data_from_file_= JSONParser().parse(stream)
         
          if (u'origin_ctime' not in _data_from_file_.keys()) or (u'origin_time' not in _data_from_file_.keys()):
            continue
          if (u'updated_ctime' not in _data_from_file_.keys()) or (u'updated_time' not in _data_from_file_.keys()):
            continue   

          # hostname define
          _host_defined_name_ = Param_container.active_devices_dict[uncode_active_device_ip]

          # get the time data to display
          start_current_time = str(_data_from_file_[u'origin_ctime'])
          end_current_time = str(_data_from_file_[u'updated_ctime'])

          start_time_time = float(_data_from_file_[u'origin_time'])
          end_time_time = float(_data_from_file_[u'updated_time'])

          # confirm the date varidation, time must be bigger
          if float(end_time_time - start_time_time) <= float(0):
            continue
          time_gab = abs(float(end_time_time - start_time_time))
          interval_string = start_current_time+"~"+end_current_time+"("+str(time_gab)+")"

          # inti the variable and make container to put in 
          origin_inform = _data_from_file_[u'origin_items'] 
          updated_inform = _data_from_file_[u'updated_items']
          origin_inform_keys = origin_inform.keys()
          updated_inform_keys = updated_inform.keys()
          _result_[uncode_active_device_ip] = {}

          for _loop2_ in updated_inform_keys:

             virservername_keyname = str(updated_inform[_loop2_][u'nestedStats'][u'entries'][u'tmName'][u'description']).strip().split("/")[-1]
             _this_value_ = parsing_from_items_with_keyname(_loop2_,origin_inform,updated_inform,time_gab,interval_string,end_time_time)
             _result_[uncode_active_device_ip].update(_this_value_)

             # var/stats file update
             indiv_stats_filename = "%(fname)s@%(device_info)s.virtual.stats" % {"device_info":str(_host_defined_name_),"fname":virservername_keyname}
             writing_file_path = str(USER_VAR_STATS+indiv_stats_filename).strip()
             if indiv_stats_filename not in filelist_updated:
               filelist_updated.append(writing_file_path)

             json_dumps_msg = json.dumps(_this_value_)

             if writing_file_path not in filelist_in_var_stats:
                f = open(writing_file_path,'w')
                f.write(json_dumps_msg+"\n")
                f.close()
             else:
                f = open(writing_file_path,'r')
                linelist = f.readlines()
                f.close()

                linelist.append(json_dumps_msg+"\n")
                index_start = int(0)
                if len(linelist) > (int(STATS_VIEWER_COUNT)*int(STATS_SAVEDDATA_MULTI)):
                  index_start = int(len(linelist) - (int(STATS_VIEWER_COUNT)*int(STATS_SAVEDDATA_MULTI)))
                 
                writing_msg_list = linelist[index_start:]

                f = open(writing_file_path,'w')
                for _wmsg_ in writing_msg_list:
                  f.write(_wmsg_.strip()+"\n")
                f.close()

       # file remove which currently not existed.
       for _fname_ in filelist_in_var_stats:
          if _fname_ not in filelist_updated: 
            bash_command = "rm -rf %(file_path)s" % {"file_path":_fname_}
            get_info = os.popen(bash_command).read().strip()

       if len(_result_.keys()) == 0:
         _result_ = "data is not enough, need to update!"
             
    except:
       # except
       message = "data perhaps was reset, need to be update."
       return Response(message, status=status.HTTP_400_BAD_REQUEST)

    return _result_ 


def transfer_restapi(active_device_ip):

    CURL_command = "curl -sk -u "+USER_NAME+":"+USER_PASSWORD+" https://"+str(active_device_ip)+"/mgmt/tm/ltm/virtual/stats/ -H 'Content-Type: application/json'"
    get_info = os.popen(CURL_command).read().strip()
    stream = BytesIO(get_info)
    data_from_CURL_command = JSONParser().parse(stream)
    virtual_stats = data_from_CURL_command[u'entries']

    # file update and data sorting
    _stats_db_ = USER_DATABASES_DIR + "stats.virtualserver."+str(active_device_ip)+".txt"
    _result_data_ = {}

    # time information to create the files
    Param_container.time_parsed_ctime = str("_".join(time.ctime().strip().split()[1:])).strip()
    Param_container.time_time = float(time.time())

    if not os.path.exists(_stats_db_):
       _result_data_[u'origin_items'] = virtual_stats
       _result_data_[u'origin_ctime'] = Param_container.time_parsed_ctime
       _result_data_[u'origin_time'] = Param_container.time_time
    else:
       f = open(_stats_db_,'r')
       _string_contents_ = f.readlines()
       f.close()
       
       # 2016 11 01 update : if len
       if len(_string_contents_):
          stream = BytesIO(_string_contents_[0])
          _data_from_file_= JSONParser().parse(stream)

          if (u'updated_items' not in _data_from_file_.keys()) or (u'updated_ctime' not in _data_from_file_.keys()) or (u'updated_time' not in _data_from_file_.keys()):
             os.popen("rm -rf "+_stats_db_)
             default_items_dict = virtual_stats 
             default_ctime = Param_container.time_parsed_ctime
             default_time_time = Param_container.time_time
          else:
             default_items_dict = _data_from_file_[u'updated_items']
             default_ctime = _data_from_file_[u'updated_ctime']
             default_time_time = _data_from_file_[u'updated_time']
          # final origin values
          _result_data_[u'origin_items'] = default_items_dict
          _result_data_[u'origin_ctime'] = default_ctime
          _result_data_[u'origin_time'] = default_time_time

    # final updates values
    _result_data_[u'updated_items'] = virtual_stats
    _result_data_[u'updated_ctime'] = Param_container.time_parsed_ctime
    _result_data_[u'updated_time'] = Param_container.time_time

    # exchange from dict to string
    result_string = json.dumps(_result_data_)
    f = open(_stats_db_,"w")
    f.write(result_string)
    f.close()
    
    # threading must have
    time.sleep(0)

@api_view(['GET','POST'])
@csrf_exempt
def f5_stats_virtual(request,format=None):

   # get method
   if request.method == 'GET':
      try:
        #return Response(get_viewer())
        message = get_viewer()
      except:
        message = ["data perhaps was deleted by error, need to be update."]
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

      return Response(message)


   elif request.method == 'POST':

      try:
        _input_ = JSONParser().parse(request)
        if re.match(ENCAP_PASSWORD,str(_input_[0]['auth_key'])):

           # log message
           f = open(LOG_FILE,"a")
           _date_ = os.popen("date").read().strip()
           log_msg = _date_+" from : "+request.META['REMOTE_ADDR']+" , method POST request to run f5_stats_virtualserver function!\n"
           f.write(log_msg)
           f.close()

           ### devicelist update at first
           # CURL_command = "curl -H \"Accept: application/json\" -X POST -d \'[{\"auth_key\":\""+ENCAP_PASSWORD+"\"}]\' http://0.0.0.0:"+RUNSERVER_PORT+"/f5/virtualserverlist/"
           # get_info = os.popen(CURL_command).read().strip()

           # read db file
           _devicelist_db_ = USER_DATABASES_DIR + "devicelist.txt"
           f = open(_devicelist_db_,'r')
           _string_contents_ = f.readlines()
           f.close()
           stream = BytesIO(_string_contents_[0])
           _data_from_devicelist_db_= JSONParser().parse(stream)

           # active server list
           for _dict_information_ in _data_from_devicelist_db_:
              if re.match('active',str(_dict_information_[u'failover'])):
                 if str(_dict_information_[u'ip']).strip() not in Param_container.active_devices_list:
                    Param_container.active_devices_list.append(str(_dict_information_[u'ip']).strip())
                    Param_container.active_devices_dict[unicode(str(_dict_information_[u'ip']).strip())] = str(_dict_information_[u'devicehostname']).strip()

           # get information
           _threads_ = []
           for _loop1_ in Param_container.active_devices_list:
              active_device_ip = str(_loop1_)
              th = threading.Thread(target=transfer_restapi, args=(active_device_ip,))
              th.start()
              _threads_.append(th)
           for th in _threads_:
              th.join()

           # get the result data and return
           return Response(get_virtual_status_info())

      except:
        message = ["data perhaps was deleted by error, need to be update."]
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

