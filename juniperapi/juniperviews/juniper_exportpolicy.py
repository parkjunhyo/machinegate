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
from juniperapi.setting import USER_VAR_NAT
from juniperapi.setting import POLICY_FILE_MAX
from juniperapi.setting import PYTHON_MULTI_PROCESS

import os,re,copy,json,time,threading,sys
import paramiko
from multiprocessing import Process, Queue, Lock

multi_access_ssh_usernumber = int(3)

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
   # 
   filename_string = "%(_hostname_)s@%(_ipaddress_)s_from_%(_from_zone_)s_to_%(_to_zone_)s_start_%(_start_count_)s.policy" % {"_ipaddress_":str(_ipaddress_),"_hostname_":str(_hostname_),"_start_count_":str(_start_count_),"_from_zone_":str(_from_zone_),"_to_zone_":str(_to_zone_)}
   save_directory = "/var/tmp/%(filename_string)s" % {"filename_string":filename_string} 
   save_command_string = "%(_command_)s | save %(save_directory)s\n" % {"save_directory":save_directory, "_command_":_command_.strip()}
   # after file save, the pattern displayed
   filesave_pattern = "Wrote [0-9]+ lines of output to \'%(save_directory)s\'" % {"save_directory":save_directory}
   #
   JUNIPER_DEVICELIST_DBFILE = USER_VAR_POLICIES + filename_string
   # connect to tranfer the command to save              
   #hold_timeout = 180
   remote_conn_pre = paramiko.SSHClient()
   remote_conn_pre.set_missing_host_key_policy(paramiko.AutoAddPolicy())
   remote_conn_pre.connect(_ipaddress_, username=USER_NAME, password=USER_PASSWORD, look_for_keys=False, allow_agent=False)
   remote_conn = remote_conn_pre.invoke_shell()
   remote_conn.settimeout(0.1)
   remote_conn.send(save_command_string)
   string_comb_list = []
   while True:
      try:
         output = remote_conn.recv(2097152)
         if output:
           string_comb_list.append(str(output))
         stringcombination = str("".join(string_comb_list))
         if re.search(filesave_pattern, stringcombination, re.I):
           string_comb_list = []
           break
      except:
         continue
   #time.sleep(hold_timeout)
   remote_conn.send("exit\n")
   time.sleep(5)
   remote_conn_pre.close()
   print "file save %(save_directory)s ... saved" % {"save_directory":save_directory}
   #
   # connect to tranfer the saved file
   #hold_timeout = 60
   remote_conn_pre = paramiko.SSHClient()
   remote_conn_pre.set_missing_host_key_policy(paramiko.AutoAddPolicy())
   remote_conn_pre.connect(_ipaddress_, username=USER_NAME, password=USER_PASSWORD, look_for_keys=False, allow_agent=False)
   remote_conn_sftp = remote_conn_pre.open_sftp()
   remote_conn_sftp.get(save_directory, JUNIPER_DEVICELIST_DBFILE)
   #time.sleep(hold_timeout)
   remote_conn_sftp.close()
   remote_conn_pre.close()
   print "file downloaded %(JUNIPER_DEVICELIST_DBFILE)s ... downloaded" % {"JUNIPER_DEVICELIST_DBFILE":JUNIPER_DEVICELIST_DBFILE}

   # 2017.01.03 removed...
   #hold_timeout = 200
   #remote_conn_pre = paramiko.SSHClient()
   #remote_conn_pre.set_missing_host_key_policy(paramiko.AutoAddPolicy())
   #remote_conn_pre.connect(_ipaddress_, username=USER_NAME, password=USER_PASSWORD, look_for_keys=False, allow_agent=False)
   #remote_conn = remote_conn_pre.invoke_shell()
   #remote_conn.send(_command_)
   #remote_conn.send("exit\n")
   #time.sleep(hold_timeout)
   #output = remote_conn.recv(2097152)
   #remote_conn_pre.close()

   # 2017.01.03 removed...
   #filename_string = "%(_hostname_)s@%(_ipaddress_)s_from_%(_from_zone_)s_to_%(_to_zone_)s_start_%(_start_count_)s.policy" % {"_ipaddress_":str(_ipaddress_),"_hostname_":str(_hostname_),"_start_count_":str(_start_count_),"_from_zone_":str(_from_zone_),"_to_zone_":str(_to_zone_)} 
   #JUNIPER_DEVICELIST_DBFILE = USER_VAR_POLICIES + filename_string
   #f = open(JUNIPER_DEVICELIST_DBFILE,"w")
   #f.write(output)
   #f.close()
   #print "%(_hostname_)s, %(_command_)s ... done/completed." % {"_command_":str(_command_),"_hostname_":str(_hostname_)}

   #
   #time.sleep(0)


def regroup_by_number(origin_list, divinterger):
   # 
   processing_combination = []
   if len(origin_list) <= int(divinterger):
     for _i_ in range(len(origin_list)):
        processing_combination.append([])
   else:
     for _i_ in range(int(divinterger)):
        processing_combination.append([])
   # 
   count = 0
   for parameter_combination in origin_list:
      (_values_, _last_) = divmod(count, int(int(divinterger)))
      processing_combination[_last_].append(parameter_combination)
      count = count + 1
   return processing_combination


def export_policy(_each_processorData_, ip_device_dict):
   #
   for _ipaddress_ in _each_processorData_:

      _hostname_ = ip_device_dict[_ipaddress_]

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

      for _command_ in export_command_list:
         run_command(_command_, fromtozone_pair, _ipaddress_, _hostname_)

      ## 2017.01.14 Code revision : SRX has some issue when multi users save the file in the device at the same time.
      ## depend on the device performace you can adjust this number below : SRX 1400 : MAX 3     
      #(_values_, _last_) = divmod(len(export_command_list),multi_access_ssh_usernumber)
      #login_number = 0
      #if int(_last_) == int(0):
      #  login_number = int(_values_)
      #else:
      #  login_number = int(_values_) + 1
      #_splited_export_command_list_ = regroup_by_number(export_command_list, login_number)

      #for _command_group_ in _splited_export_command_list_:
      #   threadlist = []
      #   for _command_ in _command_group_:
      #      _thread_ = threading.Thread(target=run_command, args=(_command_,fromtozone_pair,_ipaddress_,_hostname_,))
      #      _thread_.start()
      #      threadlist.append(_thread_)
      #   for _thread_ in threadlist:
      #      _thread_.join()

   # thread timeout 
   time.sleep(0)


def export_nat_information(_each_processorData_, ip_device_dict):
   #
   command_nat_values = {
                          "sourcenatrule" : {
                                               "filename" : "%(_hostname_)s@%(_ipaddress_)s.nat.source.rule",
                                               "clicommand" : "show security nat source rule all node primary | save"
                                            },
                          "sourcenatpool" : {
                                               "filename" : "%(_hostname_)s@%(_ipaddress_)s.nat.source.pool",
                                               "clicommand" : "show security nat source pool all node primary | save"
                                            },
                          "staticnatrule" : {
                                               "filename" : "%(_hostname_)s@%(_ipaddress_)s.nat.static.rule",
                                               "clicommand" : "show security nat static rule all node primary | save"
                                            }
                        }
   #
   for _ipaddress_ in _each_processorData_:
      _hostname_ = ip_device_dict[_ipaddress_]
      #
      command_nat_values_keyname = command_nat_values.keys()
      for _keyname_ in command_nat_values_keyname:
         default_filename = command_nat_values[_keyname_]["filename"] % {"_hostname_":str(_hostname_).strip(), "_ipaddress_":str(_ipaddress_).strip()}
         savefilename_in_device = "/var/tmp/%(default_filename)s" % {"default_filename":str(default_filename)}
         savefilename_in_remote = USER_VAR_NAT + default_filename
         # after file save, the pattern displayed
         filesave_pattern = "Wrote [0-9]+ lines of output to \'%(savefilename_in_device)s\'" % {"savefilename_in_device":savefilename_in_device}
         # connect to tranfer the command to save  
         save_command_string = "%(_default_cli_)s %(savefilename_in_device)s\n" % {"savefilename_in_device":savefilename_in_device, "_default_cli_":command_nat_values[_keyname_]["clicommand"]}
         remote_conn_pre = paramiko.SSHClient()
         remote_conn_pre.set_missing_host_key_policy(paramiko.AutoAddPolicy())
         remote_conn_pre.connect(_ipaddress_, username=USER_NAME, password=USER_PASSWORD, look_for_keys=False, allow_agent=False)
         remote_conn = remote_conn_pre.invoke_shell()
         remote_conn.settimeout(0.1)
         remote_conn.send(save_command_string)
         string_comb_list = []
         while True:
            try:
               output = remote_conn.recv(2097152)
               if output:
                 string_comb_list.append(str(output))
               stringcombination = str("".join(string_comb_list))
               if re.search(filesave_pattern, stringcombination, re.I):
                 string_comb_list = []
                 break
            except:
               continue
         remote_conn.send("exit\n")
         time.sleep(5)
         remote_conn_pre.close()
         print "file saved %(savefilename_in_device)s ... completed" % {"savefilename_in_device":savefilename_in_device}
         #
         # connect to tranfer the saved file
         #hold_timeout = 60
         remote_conn_pre = paramiko.SSHClient()
         remote_conn_pre.set_missing_host_key_policy(paramiko.AutoAddPolicy())
         remote_conn_pre.connect(_ipaddress_, username=USER_NAME, password=USER_PASSWORD, look_for_keys=False, allow_agent=False)
         remote_conn_sftp = remote_conn_pre.open_sftp()
         remote_conn_sftp.get(savefilename_in_device, savefilename_in_remote)
         #time.sleep(hold_timeout)
         remote_conn_sftp.close()
         remote_conn_pre.close()
         print "file downloaded %(savefilename_in_remote)s ... downloaded" % {"savefilename_in_remote":savefilename_in_remote}

   # thread timeout 
   time.sleep(0)

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

           # init
           processing_combination = []
           processing_combination = regroup_by_number(valid_access_ip, PYTHON_MULTI_PROCESS)
           # 
           #count = 0
           _processor_list_ = []
           for _each_processorData_ in processing_combination:
              _processor_ = Process(target = export_policy, args = (_each_processorData_, ip_device_dict,))
              _processor_.start()
              _processor_list_.append(_processor_)
           for _processor_ in _processor_list_:
              _processor_.join()
           print "policy export processors are completed..!"

           # nat information 
           _processor_list_ = []
           for _each_processorData_ in processing_combination:
              _processor_ = Process(target = export_nat_information, args = (_each_processorData_, ip_device_dict,))
              _processor_.start()
              _processor_list_.append(_processor_)
           for _processor_ in _processor_list_:
              _processor_.join()
           print "nat export processors are completed..!"

           # return
           return Response(viewer_information())

      except:
        message = "Post Algorithm has some problem!"
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

