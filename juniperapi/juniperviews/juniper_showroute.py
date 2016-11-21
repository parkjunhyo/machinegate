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


sample_msg = ['--- JUNOS 12.1X46-D40.2 built 2015-09-26 03:22:03 UTC', 'show configuration routing-options | no-more', 'show configuration interfaces | no-more', 'exit', '{secondary:node1}', 'j1002391@KRIS10-DBF02-3400FW> show configuration routing-options | no-more\rj1002391@KRIS10-DBF02-3400FW> ...ing-options | no-more                       \x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08', 'static {', '    route 10.10.77.247/32 next-hop 10.10.77.1;', '    route 10.10.77.248/32 next-hop 10.10.77.1;', '    route 10.40.54.56/32 next-hop 10.10.77.1;', '    route 10.40.54.46/32 next-hop 10.10.77.1;', '    route 10.40.54.21/32 next-hop 10.10.77.1;', '    route 10.40.54.22/32 next-hop 10.10.77.1;', '    route 10.40.54.47/32 next-hop 10.10.77.1;', '    route 10.40.54.49/32 next-hop 10.10.77.1;', '    route 10.40.71.53/32 next-hop 10.10.77.1;', '    route 10.10.68.71/32 next-hop 10.10.77.1;', '    route 10.10.68.72/32 next-hop 10.10.77.1;', '    route 10.10.77.241/32 next-hop 10.10.77.1;', '    route 10.251.16.200/32 next-hop 10.10.77.1;', '    route 0.0.0.0/0 next-hop 10.10.78.241;', '    route 10.10.32.0/19 next-hop 10.10.78.252;', '    route 172.22.208.0/23 next-hop 10.10.78.252;', '    route 172.22.210.0/24 next-hop 10.10.78.252;', '    route 172.22.212.0/22 next-hop 10.10.78.252;', '    route 172.22.224.0/23 next-hop 10.10.78.252;', '    route 172.22.228.0/24 next-hop 10.10.78.252;', '    route 172.22.237.128/27 next-hop 10.10.78.252;', '    route 172.22.237.160/27 next-hop 10.10.78.252;', '    route 172.22.211.0/24 next-hop 10.10.79.100;', '    route 10.10.77.235/32 next-hop 10.10.77.1;', '    route 10.10.88.19/32 next-hop 10.10.77.1;', '    route 10.10.64.31/32 next-hop 10.10.77.1;', '    route 10.10.64.32/32 next-hop 10.10.77.1;', '    route 172.22.136.0/24 next-hop 10.10.78.252;', '    route 172.22.137.0/24 next-hop 10.10.78.252;', '    route 172.22.138.0/24 next-hop 10.10.78.252;', '    route 172.22.139.0/24 next-hop 10.10.78.252;', '    route 172.22.140.0/24 next-hop 10.10.78.252;', '    route 172.22.141.0/24 next-hop 10.10.78.252;', '    route 172.22.142.0/24 next-hop 10.10.78.252;', '    route 172.22.143.0/24 next-hop 10.10.78.252;', '    route 10.10.12.64/32 next-hop 10.10.77.1;', '    route 10.10.12.95/32 next-hop 10.10.77.1;', '    route 10.10.30.7/32 next-hop 10.10.77.1;', '    route 10.10.68.50/32 next-hop 10.10.77.1;', '    route 10.40.65.159/32 next-hop 10.10.77.1;', '    route 10.40.51.234/32 next-hop 10.10.77.1;', '    route 10.202.208.250/32 next-hop 10.10.77.1;', '}', '', '{secondary:node1}', 'j1002391@KRIS10-DBF02-3400FW> show configuration interfaces | no-more ', 'xe-3/0/0 {', '    description PRI_1;', '    gigether-options {', '        redundant-parent reth0;', '    }', '}', 'xe-3/0/1 {', '    description PCI_1;', '    gigether-options {', '        redundant-parent reth1;', '    }', '}', 'xe-4/0/0 {', '    description DB_1_1;', '    gigether-options {', '        redundant-parent reth2;', '    }', '}', 'xe-4/0/1 {', '    description DB_1_2;', '    gigether-options {', '        redundant-parent reth2;', '    }', '}', 'xe-11/0/0 {', '    description PRI_2;', '    gigether-options {', '        redundant-parent reth0;', '    }', '}', 'xe-11/0/1 {', '    description PCI_2;', '    gigether-options {', '        redundant-parent reth1;', '    }', '}', 'xe-12/0/0 {', '    description DB_2_1;', '    gigether-options {', '        redundant-parent reth2;', '    }', '}', 'xe-12/0/1 {', '    description DB_2_2;', '    gigether-options {', '        redundant-parent reth2;', '    }', '}', 'fab0 {', '    fabric-options {', '        member-interfaces {', '            ge-0/0/10;', '            ge-0/0/11;', '        }', '    }', '}', 'fab1 {', '    fabric-options {', '        member-interfaces {', '            ge-8/0/10;', '            ge-8/0/11;', '        }', '    }', '}', 'lo0 {', '    unit 0 {', '        family inet {', '            filter {', '                input manager-ip;', '            }', '        }', '    }', '}', 'reth0 {', '    description PRI;', '    redundant-ether-options {', '        redundancy-group 1;', '    }', '    unit 0 {', '        family inet {', '            address 10.10.78.244/29;', '        }', '    }', '}', 'reth1 {', '    description PCI;', '    redundant-ether-options {', '        redundancy-group 1;', '    }', '    unit 0 {', '        family inet {', '            address 10.10.79.97/29;', '        }', '    }', '}', 'reth2 {', '    description DB;', '    redundant-ether-options {', '        redundancy-group 1;', '        lacp {', '            active;', '        }', '    }', '    unit 0 {', '        family inet {', '            address 10.10.78.249/29;', '        }', '    }', '}', '', '{secondary:node1}', 'j1002391@KRIS10-DBF02-3400FW> exit ', '', '']



def obtain_showroute(apiaccessip):
  
   #remote_conn_pre = paramiko.SSHClient()
   #remote_conn_pre.set_missing_host_key_policy(paramiko.AutoAddPolicy())
   #remote_conn_pre.connect(str(apiaccessip), username=USER_NAME, password=USER_PASSWORD, look_for_keys=False, allow_agent=False)
   #remote_conn = remote_conn_pre.invoke_shell()
   #remote_conn.send("show configuration routing-options | no-more\n")
   #remote_conn.send("show configuration interfaces | no-more\n")
   #remote_conn.send("exit\n")
   #time.sleep(PARAMIKO_DEFAULT_TIMEWAIT)
   #output = remote_conn.recv(20000)
   #remote_conn_pre.close()

   # 
   return_lines_string = sample_msg
   #return_lines_string = output.split("\r\n")

   # find route table
   pattern_string = 'route '
   route_table_list = []
   for _line_string_ in return_lines_string:
      comp_string = _line_string_.strip()
      searched_element = re.search(pattern_string,comp_string,re.I)
      if searched_element:
        if comp_string not in route_table_list:
          route_msg = comp_string.strip().split(";")[0]
          route_table_list.append(route_msg)

      
   # interface information (string parsing should be)
   pattern_start = "^[a-zA-Z0-9-/]+ {"
   pattern_end = "^}"
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

   start_end_string_list = []
   for index_list in start_end_linenumber_list:
      selective_list = return_lines_string[index_list[0]:index_list[1]]
      for _msg_string_ in selective_list:
         if re.search("redundant-parent",str(_msg_string_),re.I) or re.search("address",str(_msg_string_),re.I):
           start_end_string_list.append(selective_list)

   interface_group_by_redundant = {}
   for index_list in start_end_string_list:
      _interfacename_ = str(index_list[0].strip().split()[0]).strip()
      for _line_string_ in index_list:
         if re.search("redundant-parent",_line_string_,re.I):
           _rp_name_ = str(str(_line_string_.strip().split()[-1]).strip().split(";")[0])
           if _rp_name_ not in interface_group_by_redundant.keys():
             interface_group_by_redundant[_rp_name_] = []
             interface_group_by_redundant[_rp_name_].append(_interfacename_)
             break
           else:
             interface_group_by_redundant[_rp_name_].append(_interfacename_)
             break

   redundant_group_with_ip = {}
   for index_list in start_end_string_list:
      _interfacename_ = str(index_list[0].strip().split()[0]).strip()

      match_count = 0
      for _line_string_ in index_list:
         if re.search("redundant-ether-options",_line_string_,re.I) or re.search("address",_line_string_,re.I):
           match_count = match_count + 1      
      if match_count == 2: 
        for _line_string_ in index_list:
           if re.search("address",_line_string_,re.I):
             _if_address_ = str(str(_line_string_.strip().split()[-1]).strip().split(";")[0])
             if _interfacename_ not in redundant_group_with_ip.keys():
               redundant_group_with_ip[_interfacename_] = []
               redundant_group_with_ip[_interfacename_].append(_if_address_)
               break
             else:
               redundant_group_with_ip[_interfacename_].append(_if_address_)
               break             
 
   print route_table_list
   print redundant_group_with_ip
   print interface_group_by_redundant

           

   # thread timeout 
   time.sleep(0)
 

@api_view(['GET','POST'])
@csrf_exempt
def juniper_showroute(request,format=None):

   # file
   JUNIPER_DEVICELIST_DBFILE = USER_DATABASES_DIR + "devicelist.txt"

   # get method
   if request.method == 'GET':
      try:

         f = open(JUNIPER_DEVICELIST_DBFILE,"r")
         string_content = f.readlines()
         f.close()

         stream = BytesIO(string_content[0])
         data_from_databasefile = JSONParser().parse(stream)

         return Response(data_from_databasefile)  

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

           # find 'secondary' device list
           secondary_devicelist = []
           for _dataDict_ in data_from_CURL_command:
              _keyname_ = _dataDict_.keys()
              if (u'apiaccessip' in _keyname_) and (u'failover' in _keyname_):
                pattern_string = str(_dataDict_[u'failover']).strip()
                if re.match(pattern_string,'secondary',re.I):
                  _apiaccessip_ = _dataDict_[u'apiaccessip']
                  if _apiaccessip_ not in secondary_devicelist:
                    secondary_devicelist.append(_apiaccessip_)

           # get route table and interface information
           _threads_ = []
           for _ip_address_ in secondary_devicelist:
              th = threading.Thread(target=obtain_showroute, args=(_ip_address_,))
              th.start()
              _threads_.append(th)
           for th in _threads_:
              th.join()

           # [{u'devicename': u'KRIS10-DBF02-3400FW', u'apiaccessip': u'10.10.77.54', u'failover': u'secondary', u'mgmtip': u'10.10.77.54', u'nodename': u'node1'}]
           

           #f = open(JUNIPER_DEVICELIST_DBFILE,"r")
           #string_content = f.readlines()
           #f.close()

           #stream = BytesIO(string_content[0])
           #data_from_databasefile = JSONParser().parse(stream)


           #return_all_infolist = []
           #for dataDict_value in data_from_databasefile:

           #   dictBox = {}
           #   dictBox[u'apiaccessip'] = dataDict_value[u'apiaccessip']
           #   dictBox[u'mgmtip'] = dataDict_value[u'mgmtip']

           #   # connect              
           #   remote_conn_pre = paramiko.SSHClient()
 
           #   #
           #   remote_conn_pre.set_missing_host_key_policy(paramiko.AutoAddPolicy())
           #   remote_conn_pre.connect(dictBox[u'apiaccessip'], username=USER_NAME, password=USER_PASSWORD, look_for_keys=False, allow_agent=False)
           #   remote_conn = remote_conn_pre.invoke_shell()
           #   remote_conn.send("exit\n")
           #   time.sleep(PARAMIKO_DEFAULT_TIMEWAIT)
           #   output = remote_conn.recv(1000)
           #   remote_conn_pre.close()

           #   # active standby
           #   return_lines_string = output.split("\r\n")
           #   pattern_active_node = "{(\w+):(\w+)}"
           #   for _line_string_ in return_lines_string:
           #      searched_element = re.search(pattern_active_node,_line_string_)
           #      if searched_element:
           #        dictBox[u'failover'] = searched_element.group(1)
           #        dictBox[u'nodename'] = searched_element.group(2)
           #        break

           #   # '******@KRIS10-DBF02-3400FW>
           #   pattern_devicename = "\w+\@([a-zA-Z0-9-_]+)\>"
           #   for _line_string_ in return_lines_string:
           #      searched_element = re.search(pattern_devicename,_line_string_)
           #      if searched_element:
           #        dictBox[u'devicename'] = searched_element.group(1)
           #        break

           #   return_all_infolist.append(dictBox) 

           #f = open(JUNIPER_DEVICELIST_DBFILE,"w")
           #f.write(json.dumps(return_all_infolist))
           #f.close()
           #return Response(return_all_infolist)
           return Response("")

      except:
        message = "Post Algorithm has some problem!"
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

