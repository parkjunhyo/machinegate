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

import os,re,copy,json,time
import paramiko

class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders its content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)


@api_view(['GET','POST'])
@csrf_exempt
def juniper_devicelist(request,format=None):

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
           f = open(JUNIPER_DEVICELIST_DBFILE,"r")
           string_content = f.readlines()
           f.close()

           stream = BytesIO(string_content[0])
           data_from_databasefile = JSONParser().parse(stream)


           return_all_infolist = []
           for dataDict_value in data_from_databasefile:

              dictBox = {}
              dictBox[u'apiaccessip'] = dataDict_value[u'apiaccessip']
              dictBox[u'mgmtip'] = dataDict_value[u'mgmtip']

              # connect              
              remote_conn_pre = paramiko.SSHClient()
 
              #
              remote_conn_pre.set_missing_host_key_policy(paramiko.AutoAddPolicy())
              remote_conn_pre.connect(dictBox[u'apiaccessip'], username=USER_NAME, password=USER_PASSWORD, look_for_keys=False, allow_agent=False)
              remote_conn = remote_conn_pre.invoke_shell()
              remote_conn.send("show configuration groups | display set | match fxp\n")
              remote_conn.send("exit\n")
              time.sleep(PARAMIKO_DEFAULT_TIMEWAIT)
              output = remote_conn.recv(10000)
              remote_conn_pre.close()

              # active standby
              return_lines_string = output.split("\r\n")
              pattern_active_node = "{(\w+):(\w+)}"
              for _line_string_ in return_lines_string:
                 searched_element = re.search(pattern_active_node,_line_string_)
                 if searched_element:
                   dictBox[u'failover'] = searched_element.group(1)
                   dictBox[u'nodename'] = searched_element.group(2)
                   break

              # '******@KRIS10-DBF02-3400FW>
              pattern_devicename = "\w+\@([a-zA-Z0-9-_]+)\>"
              for _line_string_ in return_lines_string:
                 searched_element = re.search(pattern_devicename,_line_string_)
                 if searched_element:
                   dictBox[u'devicename'] = searched_element.group(1)
                   break

              # find cluster device
              pattern_devicename = "interfaces fxp"
              hadevicesip = []
              for _line_string_ in return_lines_string:
                 if re.search(pattern_devicename,_line_string_,re.I):
                   match_nodename_group = re.search("(node[0-9]+)",str(_line_string_),re.I)
                   match_nodename = match_nodename_group.group(1)
                   if not re.match(match_nodename,dictBox[u'nodename'],re.I):
                     match_ip_group = re.search("([0-9]+.[0-9]+.[0-9]+.[0-9]+/[0-9]+)",_line_string_,re.I)
                     match_ip = match_ip_group.group(1)
                     if str(match_ip) not in hadevicesip:
                       hadevicesip.append(str(match_ip))
              dictBox[u'hadevicesip'] = hadevicesip
                 
              #print return_lines_string
              return_all_infolist.append(dictBox) 

           f = open(JUNIPER_DEVICELIST_DBFILE,"w")
           f.write(json.dumps(return_all_infolist))
           f.close()
           return Response(return_all_infolist)

      except:
        message = "Post Algorithm has some problem!"
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

