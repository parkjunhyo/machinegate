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

def export_policy(_ipaddress_,_hostname_):

   # Time and size , 60s * 8 minute , 1024k * 1024m * 8 byte * 50 m
   hold_timeout = int(60 * 8)
   recv_buffersize = 1024 * 1024 * 1024
   # connect              
   remote_conn_pre = paramiko.SSHClient()
   remote_conn_pre.set_missing_host_key_policy(paramiko.AutoAddPolicy())
   remote_conn_pre.connect(_ipaddress_, username=USER_NAME, password=USER_PASSWORD, look_for_keys=False, allow_agent=False)
   remote_conn = remote_conn_pre.invoke_shell()
   remote_conn.send("show security policies detail | no-more\n")
   remote_conn.send("exit\n")
   time.sleep(hold_timeout)
   output = remote_conn.recv(recv_buffersize)
   remote_conn_pre.close()

   # file write
   filename_string = "%(_hostname_)s@%(_ipaddress_)s.policy" % {"_ipaddress_":str(_ipaddress_),"_hostname_":str(_hostname_)} 
   JUNIPER_DEVICELIST_DBFILE = USER_VAR_POLICIES + filename_string
   f = open(JUNIPER_DEVICELIST_DBFILE,"w")
   f.write(output)
   f.close()
   # thread timeout 
   time.sleep(1)

def viewer_information():
 
   filenames_list = os.listdir(USER_VAR_POLICIES)
 
   updated_filestatus = {}
   filestatus = False
   for _filename_ in filenames_list:
      searched_element = re.search("([a-zA-Z0-9\_\-]+)@([0-9]+.[0-9]+.[0-9]+.[0-9]+).policy",_filename_,re.I)
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
              th = threading.Thread(target=export_policy, args=(_ipaddress_,ip_device_dict[_ipaddress_]))
              th.start()
              _threads_.append(th)
           for th in _threads_:
              th.join()

           # return
           return Response(viewer_information())

      except:
        message = "Post Algorithm has some problem!"
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

