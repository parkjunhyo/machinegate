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
    
def runssh_clicommand(_ipaddress_, laststring_pattern, runcli_command):
   remote_conn_pre = paramiko.SSHClient()
   remote_conn_pre.set_missing_host_key_policy(paramiko.AutoAddPolicy())
   remote_conn_pre.connect(_ipaddress_, username=USER_NAME, password=USER_PASSWORD, look_for_keys=False, allow_agent=False)
   remote_conn = remote_conn_pre.invoke_shell()
   remote_conn.settimeout(0.1)
   remote_conn.send(runcli_command)
   string_comb_list = []
   interface_information = []
   while True:
      try:
         output = remote_conn.recv(2097152)
         if output:
           string_comb_list.append(str(output))
         stringcombination = str("".join(string_comb_list))
         if re.search(laststring_pattern, stringcombination, re.I):
           interface_information = copy.copy(stringcombination.split("\r\n"))
           string_comb_list = []
           break
      except:
         continue
   #time.sleep(hold_timeout)
   remote_conn.send("exit\n")
   time.sleep(5)
   remote_conn_pre.close()
   return interface_information

def obtain_deviceinfo(dataDict_value):
   dictBox = {}
   # necessary parameter
   dictBox[u'apiaccessip'] = dataDict_value[u'apiaccessip']
   dictBox[u'mgmtip'] = dataDict_value[u'mgmtip']

   ## updated at 2017.01.05
   laststring_pattern = r"\}[ \t\n\r\f\v]+\{[a-zA-Z0-9]+:[a-zA-Z0-9]+\}[ \t\n\r\f\v]+"
   interface_information = runssh_clicommand(dictBox[u'apiaccessip'], laststring_pattern, "show configuration interfaces | no-more\n")

   laststring_pattern = r"Security zone:[ \t\n\r\f\v]+[ \t\n\r\f\va-zA-Z0-9\-\./_]+[ \t\n\r\f\v]+\{[a-zA-Z0-9]+:[a-zA-Z0-9]+\}[ \t\n\r\f\v]+"
   securityzone_information = runssh_clicommand(dictBox[u'apiaccessip'], laststring_pattern, "show security zones detail | match Security | no-more\n")

   laststring_pattern = r"[0-9]+.[0-9]+.[0-9]+.[0-9]+/[0-9]+[ \t\n\r\f\v]+\{[a-zA-Z0-9]+:[a-zA-Z0-9]+\}[ \t\n\r\f\v]+"
   nodegroup_information = runssh_clicommand(dictBox[u'apiaccessip'], laststring_pattern, "show configuration groups | display set | match node | match interface | match fxp | match address\n")

   # active standby : node name and failover name 
   return_lines_string = nodegroup_information
   pattern_active_node = "{(\w+):(\w+)}"
   for _line_string_ in return_lines_string:
      searched_element = re.search(pattern_active_node,_line_string_,re.I)
      if searched_element:
        dictBox[u'failover'] = searched_element.group(1).strip()
        dictBox[u'nodeid'] = searched_element.group(2).strip()
        break

   # ******@KRIS10-DBF02-3400FW> device name finder
   return_lines_string = nodegroup_information
   pattern_devicename = "\w+\@([a-zA-Z0-9\-\./_]+)\>"
   for _line_string_ in return_lines_string:
      searched_element = re.search(pattern_devicename,_line_string_,re.I)
      if searched_element:
        dictBox[u'devicehostname'] = searched_element.group(1).strip()
        break 

   # find cluster device
   return_lines_string = nodegroup_information
   pattern_devicename = "interfaces fxp"
   hadevicesip = []
   for _line_string_ in return_lines_string:
      searched_element = re.search(pattern_devicename,_line_string_,re.I)
      if searched_element:
        match_nodename_group = re.search("set groups (node[0-9]+) interfaces",str(_line_string_),re.I)
        match_nodename = match_nodename_group.group(1)
        if not re.match(str(match_nodename).strip(),str(dictBox[u'nodeid']).strip(),re.I):
          match_ip_group = re.search("([0-9]+.[0-9]+.[0-9]+.[0-9]+/[0-9]+)",_line_string_,re.I)
          match_ip = match_ip_group.group(1)
          if str(match_ip) not in hadevicesip:
            hadevicesip.append(str(match_ip))
   dictBox[u'hadevicesip'] = hadevicesip           

   # find out the what zone does this device has and the interface name belonged to the zone.
   return_lines_string = securityzone_information
   belongzonename_list = []
   for _string_ in return_lines_string:
      cmp_string = _string_.strip()
      if re.search(r"Security zone:", cmp_string, re.I):
        foundzonename = cmp_string.split()[-1] 
        if str(foundzonename) not in belongzonename_list:
          belongzonename_list.append(str(foundzonename))
   dictBox[u'zonesname'] = belongzonename_list 
   dictBox[u'interfaces'] = {}
   for _zonename_ in dictBox[u'zonesname']:
      laststring_pattern = r"Interfaces:[ \t\n\r\f\v]+[ \t\n\r\f\va-zA-Z0-9\-\./_]+[ \t\n\r\f\v]+\{[a-zA-Z0-9]+:[a-zA-Z0-9]+\}[ \t\n\r\f\v]+"
      clicommand_string = "show security zones detail %(_zonename_)s | no-more\n" % {"_zonename_":_zonename_}
      indiviualsecurity_information = runssh_clicommand(dictBox[u'apiaccessip'], laststring_pattern, clicommand_string)
      pattern_start = "[ \t\n\r\f\v]+Interfaces:"
      pattern_end = "\{[a-zA-Z0-9]+:[a-zA-Z0-9]+\}"
      start_end_linenumber_list = start_end_parse_from_string(indiviualsecurity_information, pattern_start, pattern_end)
      for index_list in start_end_linenumber_list:
         if len(index_list) == int(2):
           selective_list = indiviualsecurity_information[index_list[0]+int(1):index_list[1]-int(1)]
           for _msg_string_ in selective_list:
              if len(str(_msg_string_).strip()) != int(0):
                if unicode(str(_msg_string_)) not in dictBox[u'interfaces'].keys():
                  dictBox[u'interfaces'][unicode(str(_msg_string_).strip())] = {}
                  dictBox[u'interfaces'][unicode(str(_msg_string_).strip())][u"zonename"] = _zonename_

   # find out the device mode : routed mode and transparent mode
   return_lines_string = interface_information
   addresspattern = r"[ \t\n\r\f\v]+address[ \t\n\r\f\v]+([0-9]+.[0-9]+.[0-9]+.[0-9]+/[0-9]+);"
   for _interfacename_ in dictBox[u'interfaces'].keys():
      pattern_start = "^([a-zA-Z0-9-/]+) {"
      pattern_end = "}"
      start_end_linenumber_list = start_end_parse_from_string(return_lines_string, pattern_start, pattern_end)
      for index_list in start_end_linenumber_list:
         selective_list = return_lines_string[index_list[0]:index_list[1]]
         interface_searchstatus = str(re.search(pattern_start, selective_list[0].strip(), re.I).group(1))

         addressip_value = []
         addressip_status = False

         if re.search(_interfacename_, interface_searchstatus, re.I) or re.search(interface_searchstatus, _interfacename_, re.I):
           #addressip_value = []
           #addressip_status = False

           for _msg_string_ in selective_list:
              #addresspattern = r"[ \t\n\r\f\v]+address[ \t\n\r\f\v]+([0-9]+.[0-9]+.[0-9]+.[0-9]+/[0-9]+);"
              searched_status = re.search(addresspattern, _msg_string_, re.I)
              if searched_status:
                addressip_status = True
                if str(searched_status.group(1).strip()) not in addressip_value:
                  addressip_value.append(str(searched_status.group(1).strip()))

           # interface mode check
           if addressip_status:
             operation_mode = "routedmode"
           else:
             operation_mode = "bridgemode"

           dictBox[u'interfaces'][unicode(_interfacename_.strip())][u'interfacemode'] = operation_mode
           dictBox[u'interfaces'][unicode(_interfacename_.strip())][u"interfaceip"] = addressip_value
           #
           if dictBox[u'interfaces'][unicode(_interfacename_.strip())][u'interfacemode'] == "bridgemode":
             for _msg_string_ in selective_list:
                accesstrunk_modepattern = "interface-mode [0-9a-zA-Z]+;"
                vlanid_pattern = "vlan-id"
                if re.search(accesstrunk_modepattern, _msg_string_.strip(), re.I):
                  dictBox[u'interfaces'][unicode(_interfacename_.strip())][u'accesstrunkstatus'] = str(_msg_string_.strip().split()[-1]).split(";")[0]
                if re.search(vlanid_pattern, _msg_string_.strip(), re.I):
                  dictBox[u'interfaces'][unicode(_interfacename_.strip())][u'vlans'] = str(_msg_string_.strip().split()[-1]).split(";")[0]
       
   # device working mode detection
   return_lines_string = interface_information
   pattern_start = "^[a-zA-Z0-9-/]+ {"
   pattern_end = "}"
   start_end_linenumber_list = start_end_parse_from_string(return_lines_string,pattern_start,pattern_end)
   dictBox[u'failovermode'] = "active_active"
   failover_mode_status = False
   for index_list in start_end_linenumber_list:
      selective_list = return_lines_string[index_list[0]:index_list[1]]
      if not failover_mode_status:
         for _msg_string_ in selective_list:
            if re.search(str("redundancy-group"),str(_msg_string_),re.I):
              failover_mode_status = True
              dictBox[u'failovermode'] = "active_standby"
              break
         #if failover_mode_status:
         #  break
   #if not failover_mode_status:
   #  dictBox[u'failovermode'] = "active_active"
 
   # optional value when mode active_standby
   if dictBox[u'failovermode'] == "active_standby":
     return_lines_string = interface_information
     pattern_start = "^([a-zA-Z0-9-/]+) {"
     pattern_end = "}"
     for _interfacename_ in dictBox[u'interfaces'].keys():
        #pattern_start = "^([a-zA-Z0-9-/]+) {"
        #pattern_end = "}"
        start_end_linenumber_list = start_end_parse_from_string(return_lines_string, pattern_start, pattern_end)
        phyinf_list = []

        redundantparent_pattern = "redundant-parent %(_interfacename_)s" % {"_interfacename_":_interfacename_}
        for index_list in start_end_linenumber_list:
           selective_list = return_lines_string[index_list[0]:index_list[1]]
           interface_searchstatus = str(re.search(pattern_start, selective_list[0].strip(), re.I).group(1))
           #redundantparent_pattern = "redundant-parent %(_interfacename_)s" % {"_interfacename_":_interfacename_}
           #redundant_mode_status = False

           for _msg_string_ in selective_list:
              cmp_string = str(_msg_string_.split(";")[0].strip())
              if re.search(cmp_string, redundantparent_pattern.strip(), re.I) or re.search(redundantparent_pattern.strip(), cmp_string, re.I):

                #redundant_mode_status = True
                if interface_searchstatus not in phyinf_list:
                  phyinf_list.append(interface_searchstatus)

        dictBox[u'interfaces'][_interfacename_][u'redundantmembers'] = phyinf_list

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

