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
from juniperapi.setting import POLICY_FILE_MAX

import os,re,copy,json,time,threading,sys
import paramiko

class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders its content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)

def start_end_parse_from_string(return_lines_string,pattern_start,pattern_end):
   start_end_linenumber_list = []
   line_index_count = 0
   temp_list_box = []
   for _line_string_ in return_lines_string:
      if re.search(pattern_start,_line_string_,re.I):
        temp_list_box.append(line_index_count)
      if re.search(pattern_end,_line_string_,re.I):
        temp_list_box.append(line_index_count)
        start_end_linenumber_list.append(temp_list_box)
        temp_list_box = []
      line_index_count = line_index_count + 1
   return start_end_linenumber_list


def run_command(_command_,fromtozone_pair,_ipaddress_,_hostname_):

   # find the all counter
   pattern_string = "show security policies from-zone ([a-zA-Z0-9\-\_\.]+) to-zone ([a-zA-Z0-9\-\_\.]+) count ([a-zA-Z0-9\-\_\.]+) start ([a-zA-Z0-9\-\_\.]+) detail | no-more\n"
   searched_value = re.search(pattern_string,_command_,re.I)
   _from_zone_ = searched_value.group(1)
   _to_zone_ = searched_value.group(2)
   _start_count_ = searched_value.group(4)
   
   max_count = POLICY_FILE_MAX
   for _dictvalue_ in fromtozone_pair:
      if re.match(str(_from_zone_),str(_dictvalue_['from']),re.I) and re.match(str(_to_zone_),str(_dictvalue_['to']),re.I):
        max_count = _dictvalue_['count']
        break

   # time parameter 60s * 4 min
   hold_timeout = 60 * 4
   # connect              
   remote_conn_pre = paramiko.SSHClient()
   remote_conn_pre.set_missing_host_key_policy(paramiko.AutoAddPolicy())
   remote_conn_pre.connect(_ipaddress_, username=USER_NAME, password=USER_PASSWORD, look_for_keys=False, allow_agent=False)
   remote_conn = remote_conn_pre.invoke_shell()
   remote_conn.send(_command_)
   remote_conn.send("exit\n")
   time.sleep(hold_timeout)
   output = remote_conn.recv(2097152)
   remote_conn_pre.close()

   # file write
   filename_string = "%(_hostname_)s@%(_ipaddress_)s_from_%(_from_zone_)s_to_%(_to_zone_)s_start_%(_start_count_)s.policy" % {"_ipaddress_":str(_ipaddress_),"_hostname_":str(_hostname_),"_start_count_":str(_start_count_),"_from_zone_":str(_from_zone_),"_to_zone_":str(_to_zone_)} 
   JUNIPER_DEVICELIST_DBFILE = USER_VAR_POLICIES + filename_string
   f = open(JUNIPER_DEVICELIST_DBFILE,"w")
   f.write(output)
   f.close()
   # thread timeout 
   time.sleep(1) 

 

def export_policy(_ipaddress_,_hostname_):

   # connect 
   remote_conn_pre = paramiko.SSHClient()
   remote_conn_pre.set_missing_host_key_policy(paramiko.AutoAddPolicy())
   remote_conn_pre.connect(_ipaddress_, username=USER_NAME, password=USER_PASSWORD, look_for_keys=False, allow_agent=False)
   remote_conn = remote_conn_pre.invoke_shell()
   remote_conn.send("show security policies zone-context | no-more\n")
   remote_conn.send("exit\n")
   time.sleep(PARAMIKO_DEFAULT_TIMEWAIT)
   output = remote_conn.recv(20000)
   remote_conn_pre.close() 

   return_lines_string = output.split("\r\n")
   pattern_start = "From zone[ \t\n\r\f\v]+To zone[ \t\n\r\f\v]+Policy count+"
   pattern_end = "%(_hostname_)s> exit" % {"_hostname_":_hostname_}
   start_end_linenumber_list = start_end_parse_from_string(return_lines_string,pattern_start,pattern_end)
 
   fromtozone_pair = []
   for _indexlist_ in start_end_linenumber_list:
      string_line = return_lines_string[_indexlist_[0]+1:_indexlist_[-1]-1]
      for _line_ in string_line:
         list_line = _line_.strip().split()
         dictBox = {}
         if len(list_line) == 3:
           dictBox["from"] = list_line[0]
           dictBox["to"] = list_line[1]
           dictBox["count"] = list_line[2]
           fromtozone_pair.append(dictBox)

   # create command : POLICY_FILE_MAX, show security policies from-zone PRI to-zone COM count 100 start 100 | no-more
   export_command_list = [] 
   for _dictvalue_ in fromtozone_pair:
      # parameter
      _policy_count_ = int(_dictvalue_["count"])
      div_count = int(_policy_count_/POLICY_FILE_MAX)
      _from_zone_ = str(_dictvalue_["from"])
      _to_zone_ = str(_dictvalue_["to"])
      # create command
      if div_count <= int(0):
        _command_ = "show security policies from-zone %(_from_)s to-zone %(_to_)s count %(_maxcount_)s start %(_start_)s detail | no-more\n" % {"_from_":_from_zone_,"_to_":_to_zone_,"_maxcount_":str(_policy_count_),"_start_":str(1)}
        export_command_list.append(_command_)
      else:
        _mod_value_ = int(_policy_count_ % POLICY_FILE_MAX)
        if _mod_value_ == int(0):
          list_range = range(div_count)
        else:
          list_range = range(div_count+1)
        for _i_ in list_range:
           start_value = int((POLICY_FILE_MAX * _i_) + 1)
           _command_ = "show security policies from-zone %(_from_)s to-zone %(_to_)s count %(_maxcount_)s start %(_start_)s detail | no-more\n" % {"_from_":_from_zone_,"_to_":_to_zone_,"_maxcount_":str(POLICY_FILE_MAX),"_start_":str(start_value)}
           export_command_list.append(_command_)

   # depend on the device performace you can adjust this number below      
   multi_access_ssh_usernumber = int(4)     
   ( _divnumber_, _modnumber_ ) = divmod(len(export_command_list),multi_access_ssh_usernumber)
   _loopinglist_ = []
   if int(_modnumber_) == int(0):
     _looptotalcount_ = int(_divnumber_)
   else:
     _looptotalcount_ = int(_divnumber_) + 1
   _loopinglist_ = range(_looptotalcount_)
    
   _loopcount_ = 1
   for _loopid_ in _loopinglist_:
      _splited_export_command_list_ = [] 
      _start_id_ = int(_loopid_) * int(multi_access_ssh_usernumber)
      _end_id_ = ( int(_loopid_) + 1 ) * int(multi_access_ssh_usernumber)
      if int(_loopcount_) != int(_looptotalcount_):
        _splited_export_command_list_ = export_command_list[_start_id_:_end_id_]
      else:
        _splited_export_command_list_ = export_command_list[_start_id_:]        
      _loopcount_ = _loopcount_ + 1 
    
      _threads_ = []
      for _command_ in _splited_export_command_list_:      
         th = threading.Thread(target=run_command, args=(_command_,fromtozone_pair,_ipaddress_,_hostname_,))
         th.start()
         _threads_.append(th)
      for th in _threads_:
         th.join()   



   #_threads_ = []
   #for _command_ in export_command_list:      
   #   th = threading.Thread(target=run_command, args=(_command_,fromtozone_pair,_ipaddress_,_hostname_,))
   #   th.start()
   #   _threads_.append(th)
   #for th in _threads_:
   #   th.join()   

   # thread timeout 
   time.sleep(10)

def viewer_information():
   filenames_list = os.listdir(USER_VAR_POLICIES)
   updated_filestatus = {}
   filestatus = False
   for _filename_ in filenames_list:
      searched_element = re.search("([a-zA-Z0-9\_\-]+)@([0-9]+.[0-9]+.[0-9]+.[0-9]+)_[a-zA-Z0-9\_\-\. \t\n\r\f\v]+.policy",_filename_,re.I)
      if searched_element:
        filepath = USER_VAR_POLICIES + _filename_
        updated_filestatus[str(_filename_)] = str(time.ctime(os.path.getmtime(filepath)))
        filestatus = True

   if not filestatus:
     return ["error, export the policy!"] 

   return updated_filestatus 


@api_view(['GET','POST'])
@csrf_exempt
def juniper_exportpolicy(request,format=None):

   JUNIPER_DEVICELIST_DBFILE = USER_DATABASES_DIR + "devicelist.txt"

   # get method
   if request.method == 'GET':
      try:

         return Response(viewer_information())

      except:
         message = ["device list database is not existed!"]
         return Response(message, status=status.HTTP_400_BAD_REQUEST)


   elif request.method == 'POST':

      try:
        _input_ = JSONParser().parse(request)

        if re.match(ENCAP_PASSWORD,str(_input_[0]['auth_key'])):

           # log message
           #f = open(LOG_FILE,"a")
           #_date_ = os.popen("date").read().strip()
           #log_msg = _date_+" from : "+request.META['REMOTE_ADDR']+" , method POST request to run f5_devicelist function!\n"
           #f.write(log_msg)
           #f.close()

           # device file read
           CURL_command = "curl http://0.0.0.0:"+RUNSERVER_PORT+"/juniper/devicelist/"
           get_info = os.popen(CURL_command).read().strip()
           stream = BytesIO(get_info)
           data_from_CURL_command = JSONParser().parse(stream)

           valid_access_ip = []
           ip_device_dict = {}
           for dataDict_value in data_from_CURL_command:
              _keyname_ = dataDict_value.keys()
              if (u"failover" not in _keyname_) or ("failover" not in _keyname_):
                return Response("error, device list should be updated!", status=status.HTTP_400_BAD_REQUEST)
              else:
                searched_element = re.search(str("secondary"),str(dataDict_value[u"failover"]),re.I)
                if searched_element:
                  _ipaddress_ = str(dataDict_value[u"apiaccessip"])
                  if _ipaddress_ not in valid_access_ip:
                    ip_device_dict[_ipaddress_] = str(dataDict_value[u"devicehostname"])
                    valid_access_ip.append(_ipaddress_)

           _threads_ = []
           for _ipaddress_ in valid_access_ip:
              th = threading.Thread(target=export_policy, args=(_ipaddress_,ip_device_dict[_ipaddress_],))
              th.start()
              _threads_.append(th)
           for th in _threads_:
              th.join()

           # return
           return Response(viewer_information())

      except:
        message = "Post Algorithm has some problem!"
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

