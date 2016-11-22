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


def obtain_showroute(apiaccessip,device_information_values):

   # find matched mgmt
   for _dataDict_ in device_information_values:
      if re.match(str(_dataDict_[u"apiaccessip"]),str(apiaccessip)):
        devicemgmtip = str(_dataDict_[u"mgmtip"]).strip()

   # interface : zone, category
   interface_zone_dict = {}
   for _dataDict_ in device_information_values:
      if re.match(str(_dataDict_[u"apiaccessip"]),str(apiaccessip)):
        for _keyname_ in _dataDict_[u"interfaces"].keys():
           interface_zone_dict[str(_keyname_)] = str(_dataDict_[u"interfaces"][_keyname_][u"zonename"])

   # ssh access 
   remote_conn_pre = paramiko.SSHClient()
   remote_conn_pre.set_missing_host_key_policy(paramiko.AutoAddPolicy())
   remote_conn_pre.connect(str(apiaccessip), username=USER_NAME, password=USER_PASSWORD, look_for_keys=False, allow_agent=False)
   remote_conn = remote_conn_pre.invoke_shell()
   remote_conn.send("show route | no-more\n")
   remote_conn.send("exit\n")
   time.sleep(PARAMIKO_DEFAULT_TIMEWAIT)
   output = remote_conn.recv(40000)
   remote_conn_pre.close()

   # 
   return_lines_string = output.split("\r\n")
   pattern_start= "^[0-9]+.[0-9]+.[0-9]+.[0-9]+/[0-9]+"
   pattern_end = "via [a-zA-Z0-9\.]+$"
   start_end_linenumber_list = start_end_parse_from_string(return_lines_string,pattern_start,pattern_end)

   return_all = []
   for index_list in start_end_linenumber_list:

      _string_ = str(return_lines_string[index_list[0]]).strip()
      routing_table = str(_string_.split()[0]).strip()

      pattern_route = "\[([a-zA-Z0-9]+)/[a-zA-Z0-9]+\]"
      route_status = re.search(pattern_route,_string_,re.I).group(1)

      _string_ = str(return_lines_string[index_list[-1]]).strip()
      pattern_route = "> to ([0-9]+.[0-9]+.[0-9]+.[0-9]+)"
      
      searched_element = re.search(pattern_route,_string_,re.I)
      if searched_element:
        nexthop_ip = str(searched_element.group(1)).strip()
      else:
        nexthop_ip = "none"
   
      pattern_route = "via ([a-zA-Z0-9\.]+)$"
      nexthop_int = re.search(pattern_route,_string_,re.I).group(1)      
 
      zone_name = "none"
      for _keyname_ in interface_zone_dict.keys():
         if re.search(str(_keyname_),str(nexthop_int),re.I):
           zone_name = interface_zone_dict[_keyname_]
           break
      #
      dictBox = {}
      if routing_table not in dictBox.keys():
        dictBox[routing_table] = {}
        dictBox[routing_table]["routeproperty"] = route_status
        dictBox[routing_table]["nexthopip"] = nexthop_ip
        dictBox[routing_table]["nexthopinterface"] = nexthop_int
        dictBox[routing_table]["zonename"] = zone_name
        return_all.append(dictBox)
         
   # file write
   filename_string = "routingtable_%(_ipaddr_)s.txt" % {"_ipaddr_":devicemgmtip} 
   JUNIPER_DEVICELIST_DBFILE = USER_DATABASES_DIR + filename_string
   f = open(JUNIPER_DEVICELIST_DBFILE,"w")
   f.write(json.dumps(return_all))
   f.close()
    
   # thread timeout 
   time.sleep(1)

def viewer_information():
   filenames_list = os.listdir(USER_DATABASES_DIR)
   valid_filename = []
   return_values = []
   for _filename_ in filenames_list:
      searched_element = re.search("routingtable_[0-9]+.[0-9]+.[0-9]+.[0-9]+.txt",_filename_,re.I)
      if searched_element:
        if str(_filename_) not in valid_filename:
          valid_filename.append(str(_filename_))

   if len(valid_filename) == int(0):
     return ["error, no routing table database, try updated!"]
   else:
     for _filename_ in valid_filename:
        JUNIPER_DEVICELIST_DBFILE = USER_DATABASES_DIR + str(_filename_)
        f = open(JUNIPER_DEVICELIST_DBFILE,"r")
        string_content = f.readlines()
        f.close()
        stream = BytesIO(string_content[0])
        data_from_databasefile = JSONParser().parse(stream)
        dictbox_temp = {}
        dictbox_temp[str(re.search("([0-9]+.[0-9]+.[0-9]+.[0-9]+)",str(_filename_),re.I).group(1)).strip()] = data_from_databasefile
        return_values.append(dictbox_temp)

   return return_values
   

@api_view(['GET','POST'])
@csrf_exempt
def juniper_showroute(request,format=None):

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

           # device information
           device_information_values = copy.copy(data_from_CURL_command)

           # find 'primary/secondary' device list
           post_algorithm_status = False
           primarysecondary_devicelist = []
           for _dataDict_ in data_from_CURL_command:
              _keyname_ = _dataDict_.keys()
              if (u'apiaccessip' in _keyname_) and (u'failover' in _keyname_):
                pattern_string = str(_dataDict_[u'failover']).strip()
                if re.match(pattern_string,'primary',re.I):
                  _apiaccessip_ = _dataDict_[u'apiaccessip']
                  if _apiaccessip_ not in primarysecondary_devicelist:
                    primarysecondary_devicelist.append(_apiaccessip_)
                    post_algorithm_status = True
           
           if not post_algorithm_status:
             message = ["error, device list should be updated!"]
             return Response(message, status=status.HTTP_400_BAD_REQUEST)

           # get route table and interface information
           _threads_ = []
           for _ip_address_ in primarysecondary_devicelist:
              th = threading.Thread(target=obtain_showroute, args=(_ip_address_,device_information_values))
              th.start()
              _threads_.append(th)
           for th in _threads_:
              th.join()

           return Response(viewer_information())

      except:
        message = "Post Algorithm has some problem!"
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

