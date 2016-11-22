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
from juniperapi.setting import PARAMIKO_DEFAULT_TIMEWAIT

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
      if re.match(pattern_start,_line_string_,re.I):
        temp_list_box.append(line_index_count)
      if re.match(pattern_end,_line_string_,re.I):
        temp_list_box.append(line_index_count)
        start_end_linenumber_list.append(temp_list_box)
        temp_list_box = []
      line_index_count = line_index_count + 1
   return start_end_linenumber_list
    

def obtain_deviceinfo(dataDict_value):
   dictBox = {}
   # necessary parameter
   dictBox[u'apiaccessip'] = dataDict_value[u'apiaccessip']
   dictBox[u'mgmtip'] = dataDict_value[u'mgmtip']
   # connect              
   remote_conn_pre = paramiko.SSHClient()
   remote_conn_pre.set_missing_host_key_policy(paramiko.AutoAddPolicy())
   remote_conn_pre.connect(dictBox[u'apiaccessip'], username=USER_NAME, password=USER_PASSWORD, look_for_keys=False, allow_agent=False)
   remote_conn = remote_conn_pre.invoke_shell()
   remote_conn.send("show configuration groups | display set | match fxp\n")
   remote_conn.send("show configuration interfaces | no-more\n")
   remote_conn.send("show configuration security zones | display set | match interface | no-more\n")
   remote_conn.send("exit\n")
   time.sleep(PARAMIKO_DEFAULT_TIMEWAIT)
   output = remote_conn.recv(20000)
   remote_conn_pre.close()
   # active standby
   return_lines_string = output.split("\r\n")
   pattern_active_node = "{(\w+):(\w+)}"
   for _line_string_ in return_lines_string:
      searched_element = re.search(pattern_active_node,_line_string_,re.I)
      if searched_element:
        dictBox[u'failover'] = searched_element.group(1)
        dictBox[u'nodeid'] = searched_element.group(2)
        break
   # ******@KRIS10-DBF02-3400FW> device name finder
   pattern_devicename = "\w+\@([a-zA-Z0-9-_]+)\>"
   for _line_string_ in return_lines_string:
      searched_element = re.search(pattern_devicename,_line_string_,re.I)
      if searched_element:
        dictBox[u'devicehostname'] = searched_element.group(1)
        break 
   # find cluster device
   pattern_devicename = "interfaces fxp"
   hadevicesip = []
   for _line_string_ in return_lines_string:
      searched_element = re.search(pattern_devicename,_line_string_,re.I)
      if searched_element:
        match_nodename_group = re.search("(node[0-9]+)",str(_line_string_),re.I)
        match_nodename = match_nodename_group.group(1)
        if not re.match(str(match_nodename).strip(),str(dictBox[u'nodeid']).strip(),re.I):
          match_ip_group = re.search("([0-9]+.[0-9]+.[0-9]+.[0-9]+/[0-9]+)",_line_string_,re.I)
          match_ip = match_ip_group.group(1)
          if str(match_ip) not in hadevicesip:
            hadevicesip.append(str(match_ip))
   dictBox[u'hadevicesip'] = hadevicesip           
   # interface information (string parsing should be)
   pattern_start = "^[a-zA-Z0-9-/]+ {"
   pattern_end = "^}"
   start_end_linenumber_list = start_end_parse_from_string(return_lines_string,pattern_start,pattern_end)
   # interface information only
   start_end_string_list = []
   for index_list in start_end_linenumber_list:
      selective_list = return_lines_string[index_list[0]:index_list[1]]
      for _msg_string_ in selective_list:
         if re.search(str("redundant-parent"),str(_msg_string_),re.I) or re.search(str("redundant-ether-options"),str(_msg_string_),re.I):
           start_end_string_list.append(selective_list)
           break
   # interface name with redenent group
   interface_group_by_redundant = {}
   for index_list in start_end_string_list:
      _interfacename_ = str(index_list[0].strip().split()[0]).strip()
      for _line_string_ in index_list:
         searched_element = re.search("redundant-parent",_line_string_,re.I)
         if searched_element:
           _rp_name_ = str(str(_line_string_.strip().split()[-1]).strip().split(";")[0])
           if _rp_name_ not in interface_group_by_redundant.keys():
             interface_group_by_redundant[_rp_name_] = []
           interface_group_by_redundant[_rp_name_].append(_interfacename_)
           break 
   # redenent group with ip
   redundant_group_with_ip = {}
   for index_list in start_end_string_list:
      _interfacename_ = str(index_list[0].strip().split()[0]).strip()
      match_count = 0
      for _line_string_ in index_list:
         if re.search("redundant-ether-options",_line_string_,re.I) or re.search("address",_line_string_,re.I):
           match_count = match_count + 1
      if match_count == 2:
        for _line_string_ in index_list:
           searched_element = re.search("address",_line_string_,re.I)
           if searched_element:
             _if_address_ = str(str(_line_string_.strip().split()[-1]).strip().split(";")[0])
             if _interfacename_ not in redundant_group_with_ip.keys():
               redundant_group_with_ip[_interfacename_] = []
             redundant_group_with_ip[_interfacename_].append(_if_address_)
             break
   # findout zone name
   redundant_values = interface_group_by_redundant.keys()
   pattern_string = "^set security zones security-zone ([a-zA-Z0-9\_\-]+) interfaces %(_redundant_)s"
   interface_information = {}
   for _redundant_value_ in redundant_values:
      _redundant_ = str(_redundant_value_)
      # basic information
      interface_information[_redundant_] = {}
      interface_information[_redundant_][str("phy")] = []
      interface_information[_redundant_][str("phy")] = interface_group_by_redundant[_redundant_]
      interface_information[_redundant_][str("interfaceip")] = []
      interface_information[_redundant_][str("interfaceip")] = redundant_group_with_ip[_redundant_]  
      pattern_zone = pattern_string % {"_redundant_":_redundant_}
      for _line_string_ in return_lines_string:
         searched_element = re.search(pattern_zone,str(_line_string_),re.I)
         if searched_element:
           interface_information[_redundant_][str("zonename")] = str(searched_element.group(1))
   dictBox[u'interfaces'] = interface_information
   # file write
   filename_string = "deviceinfo_%(_ipaddr_)s.txt" % {"_ipaddr_":str(dataDict_value[u'mgmtip'])} 
   JUNIPER_DEVICELIST_DBFILE = USER_DATABASES_DIR + filename_string
   f = open(JUNIPER_DEVICELIST_DBFILE,"w")
   f.write(json.dumps(dictBox))
   f.close()
   # thread timeout 
   time.sleep(1)

def viewer_information():
 
   filenames_list = os.listdir(USER_DATABASES_DIR)
   valid_filename = [] 
   return_values = []
   for _filename_ in filenames_list:
      searched_element = re.search("deviceinfo_[0-9]+.[0-9]+.[0-9]+.[0-9]+.txt",_filename_,re.I)
      if searched_element:
        if str(_filename_) not in valid_filename:
          valid_filename.append(str(_filename_))
   if len(valid_filename) == 0:
     JUNIPER_DEVICELIST_DBFILE = USER_DATABASES_DIR + "devicelist.txt"
     f = open(JUNIPER_DEVICELIST_DBFILE,"r")
     string_content = f.readlines()
     f.close()
     stream = BytesIO(string_content[0])
     data_from_databasefile = JSONParser().parse(stream)
     return data_from_databasefile
   else:
     for _filename_ in valid_filename:
        JUNIPER_DEVICELIST_DBFILE = USER_DATABASES_DIR + str(_filename_)
        f = open(JUNIPER_DEVICELIST_DBFILE,"r")
        string_content = f.readlines()
        f.close()
        stream = BytesIO(string_content[0])
        data_from_databasefile = JSONParser().parse(stream)
        return_values.append(data_from_databasefile)
        
   return return_values 


@api_view(['GET','POST'])
@csrf_exempt
def juniper_devicelist(request,format=None):

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
           f = open(JUNIPER_DEVICELIST_DBFILE,"r")
           string_content = f.readlines()
           f.close()

           stream = BytesIO(string_content[0])
           data_from_databasefile = JSONParser().parse(stream)

           _threads_ = []
           for dataDict_value in data_from_databasefile:
              th = threading.Thread(target=obtain_deviceinfo, args=(dataDict_value,))
              th.start()
              _threads_.append(th)
           for th in _threads_:
              th.join()

           # return
           return Response(viewer_information())

      except:
        message = "Post Algorithm has some problem!"
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

