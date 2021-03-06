from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.renderers import JSONRenderer
from rest_framework.parsers import JSONParser

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils.six import BytesIO

#from juniperapi.setting import USER_DATABASES_DIR
from juniperapi.setting import USER_NAME
from juniperapi.setting import USER_PASSWORD
from juniperapi.setting import ENCAP_PASSWORD
from juniperapi.setting import RUNSERVER_PORT
from juniperapi.setting import PARAMIKO_DEFAULT_TIMEWAIT
from juniperapi.setting import USER_VAR_POLICIES
from juniperapi.setting import USER_VAR_NAT
from juniperapi.setting import POLICY_FILE_MAX
from juniperapi.setting import PYTHON_MULTI_PROCESS
from juniperapi.setting import system_property
from juniperapi.setting import USER_VAR_ADDRESSBOOK
from juniperapi.setting import USER_VAR_APPLICATIONS

import os,re,copy,json,time,threading,sys
import os.path
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

from shared_function import obtainjson_from_mongodb as obtainjson_from_mongodb
from shared_function import findout_primary_devices as findout_primary_devices
from shared_function import exact_findout as exact_findout
from shared_function import sftp_file_download as sftp_file_download
from shared_function import runssh_clicommand as runssh_clicommand

#def export_policy(_primaryip_, secondary_devices, this_processor_queue):
#def export_policy(_primaryip_, primary_detail_info, this_processor_queue):
#def export_policy(_primaryip_, this_processor_queue):
def export_policy(_primaryString_):
   # policy
   #_primary_hostname_ = secondary_devices["primary_hostname"]
   #_accessip_ = secondary_devices["selected_hadevicesip"]
   #_zones_namelist_ = secondary_devices["selected_zonenames"]

   # 
   _splitedInput_ = _primaryString_.strip().split('::')
   _deviceHostName_ = _splitedInput_[0]
   _primaryip_ = _splitedInput_[-1]

   #_deviceHostNameFromDB_ = exact_findout('juniperSrx_registeredDevices',{"apiaccessip":str(_primaryip_)})
   #_deviceHostName_ = str(_deviceHostNameFromDB_[0][u'hostname'])

   # primaryAll_info = exact_findout('juniperSrx_devicesInfomation',{"failover" : "primary"})
   _fromDB_values_ = exact_findout('juniperSrx_devicesInfomation', {'apiaccessip':str(_primaryip_), 'zoneValidation':'enable'})
   for _dictValue_ in _fromDB_values_:
      _cmdValues_ = {}
      _cmdValues_['hostname'] = str(_dictValue_[u'hostname'])
      _cmdValues_['from_zone'] = str(_dictValue_[u'from_zone'])
      _cmdValues_['to_zone'] = str(_dictValue_[u'to_zone'])
      #
      saveFileName = "/var/tmp/from_%(from_zone)s_to_%(to_zone)s" % _cmdValues_
      _cmdValues_['saveFileName'] = saveFileName
      _thisCmd_ = "show security policies detail from-zone %(from_zone)s to-zone %(to_zone)s | no-more | save %(saveFileName)s\n" % _cmdValues_
      _lastString_ = "Wrote [0-9]* line[s]* of output to \'%(saveFileName)s\'[ \t\n\r\f\v]+\{[a-zA-Z0-9]+:[a-zA-Z0-9]+\}[ \t\n\r\f\v]+" % _cmdValues_
      #
      remoteSaveFileName = USER_VAR_POLICIES + "from_%(from_zone)s_to_%(to_zone)s@%(hostname)s" % _cmdValues_
      #
      runssh_clicommand(str(_primaryip_), _lastString_, _thisCmd_)
      sftp_file_download(str(_primaryip_), saveFileName, remoteSaveFileName)
      
   #
   _fromDB_values_ = exact_findout('juniperSrx_zonestatus', {'apiaccessip':str(_primaryip_), 'status':'on'})
   for _dictValue_ in _fromDB_values_:
      _cmdValues_ = {}
      _cmdValues_['hostname'] = str(_dictValue_[u'hostname'])
      _cmdValues_['zonename'] = str(_dictValue_[u'zonename'])
      #
      saveFileName = "/var/tmp/this_Addressbook" % _cmdValues_
      _cmdValues_['saveFileName'] = saveFileName
      #
      _thisCmd_ = "show configuration security zones security-zone %(zonename)s address-book | no-more | save %(saveFileName)s\n" % _cmdValues_
      _lastString_ = "Wrote [0-9]* line[s]* of output to \'%(saveFileName)s\'[ \t\n\r\f\v]+\{[a-zA-Z0-9]+:[a-zA-Z0-9]+\}[ \t\n\r\f\v]+" % _cmdValues_
      remoteSaveFileName = USER_VAR_ADDRESSBOOK + "%(zonename)s@%(hostname)s" % _cmdValues_
      #
      runssh_clicommand(str(_primaryip_), _lastString_, _thisCmd_)
      sftp_file_download(str(_primaryip_), saveFileName, remoteSaveFileName)

   # show configuration applications
   _cmdValues_ = {}
   _cmdValues_['hostname'] = _deviceHostName_
   saveFileName = "/var/tmp/this_application"
   _cmdValues_['saveFileName'] = saveFileName
   # 
   _thisCmd_ = "show configuration applications | no-more | save %(saveFileName)s\n" % _cmdValues_
   _lastString_ = "Wrote [0-9]* line[s]* of output to \'%(saveFileName)s\'[ \t\n\r\f\v]+\{[a-zA-Z0-9]+:[a-zA-Z0-9]+\}[ \t\n\r\f\v]+" % _cmdValues_
   remoteSaveFileName = USER_VAR_APPLICATIONS + "application@%(hostname)s" % _cmdValues_
   #
   runssh_clicommand(str(_primaryip_), _lastString_, _thisCmd_)
   sftp_file_download(str(_primaryip_), saveFileName, remoteSaveFileName)
   
   # show configuration applications
   _cmdValues_ = {}
   _cmdValues_['hostname'] = _deviceHostName_
   saveFileName = "/var/tmp/this_default_application"
   _cmdValues_['saveFileName'] = saveFileName
   # 
   _thisCmd_ = "show configuration groups junos-defaults applications | no-more | save %(saveFileName)s\n" % _cmdValues_
   _lastString_ = "Wrote [0-9]* line[s]* of output to \'%(saveFileName)s\'[ \t\n\r\f\v]+\{[a-zA-Z0-9]+:[a-zA-Z0-9]+\}[ \t\n\r\f\v]+" % _cmdValues_
   remoteSaveFileName = USER_VAR_APPLICATIONS + "default_application@%(hostname)s" % _cmdValues_
   #
   runssh_clicommand(str(_primaryip_), _lastString_, _thisCmd_)
   sftp_file_download(str(_primaryip_), saveFileName, remoteSaveFileName)

   # show security nat source rule all node primary
   _cmdValues_ = {}
   _cmdValues_['hostname'] = _deviceHostName_
   saveFileName = "/var/tmp/this_sourcerule"
   _cmdValues_['saveFileName'] = saveFileName
   # 
   _thisCmd_ = "show security nat source rule all node primary | no-more | save %(saveFileName)s\n" % _cmdValues_
   _lastString_ = "Wrote [0-9]* line[s]* of output to \'%(saveFileName)s\'[ \t\n\r\f\v]+\{[a-zA-Z0-9]+:[a-zA-Z0-9]+\}[ \t\n\r\f\v]+" % _cmdValues_
   remoteSaveFileName = USER_VAR_NAT + "sourcerule@%(hostname)s" % _cmdValues_
   #
   runssh_clicommand(str(_primaryip_), _lastString_, _thisCmd_)
   sftp_file_download(str(_primaryip_), saveFileName, remoteSaveFileName)
 
   # show security nat source pool all node primary
   _cmdValues_ = {}
   _cmdValues_['hostname'] = _deviceHostName_
   saveFileName = "/var/tmp/this_sourcepool"
   _cmdValues_['saveFileName'] = saveFileName 
   #
   _thisCmd_ = "show security nat source pool all node primary | no-more | save %(saveFileName)s\n" % _cmdValues_
   _lastString_ = "Wrote [0-9]* line[s]* of output to \'%(saveFileName)s\'[ \t\n\r\f\v]+\{[a-zA-Z0-9]+:[a-zA-Z0-9]+\}[ \t\n\r\f\v]+" % _cmdValues_
   remoteSaveFileName = USER_VAR_NAT + "sourcepool@%(hostname)s" % _cmdValues_
   #
   runssh_clicommand(str(_primaryip_), _lastString_, _thisCmd_)
   sftp_file_download(str(_primaryip_), saveFileName, remoteSaveFileName)

   # show security nat static rule all node primary
   _cmdValues_ = {}
   _cmdValues_['hostname'] = _deviceHostName_
   saveFileName = "/var/tmp/this_staticrule"
   _cmdValues_['saveFileName'] = saveFileName
   #
   _thisCmd_ = "show security nat static rule all node primary | no-more | save %(saveFileName)s\n" % _cmdValues_
   _lastString_ = "Wrote [0-9]* line[s]* of output to \'%(saveFileName)s\'[ \t\n\r\f\v]+\{[a-zA-Z0-9]+:[a-zA-Z0-9]+\}[ \t\n\r\f\v]+" % _cmdValues_
   remoteSaveFileName = USER_VAR_NAT + "staticrule@%(hostname)s" % _cmdValues_
   #
   runssh_clicommand(str(_primaryip_), _lastString_, _thisCmd_)
   sftp_file_download(str(_primaryip_), saveFileName, remoteSaveFileName)


   # return the queue {'apiaccessip':str(_primaryip_), 'zoneValidation':'enable'}
   #return_object = {
   #     "items":[],
   #     "process_status":"done",
   #     "process_msg":"%(hostname)s configuration exported" % {'hostname':str(_deviceHostName_)}
   #}
   #this_processor_queue.put(return_object)

   #done_msg = "%(_this_hostname_)s exported!" % {"_this_hostname_":_primary_hostname_}
   #this_processor_queue.put({"message":done_msg,"process_status":"done"})

   # thread timeout 
   time.sleep(1)



@api_view(['POST'])
@csrf_exempt
def juniper_exportpolicy(request,format=None):

   if request.method == 'POST':
     if re.search(r"system", system_property["role"], re.I):
       _input_ = JSONParser().parse(request)
       # confirm input type 
       if type(_input_) != type({}):
         return_object = {
              "items":[],
              "process_status":"error",
              "process_msg":"input wrong format"
         }
         return Response(json.dumps(return_object))
       # confirm auth
       if ('auth_key' not in _input_.keys()) and (u'auth_key' not in _input_.keys()):
         return_object = {
              "items":[],
              "process_status":"error",
              "process_msg":"no auth_password"
         }
         return Response(json.dumps(return_object))
       # 
       auth_matched = re.match(ENCAP_PASSWORD, _input_['auth_key'])

       print "run"

       if auth_matched:
       # end of if auth_matched:
         #device_information_values = obtainjson_from_mongodb('juniper_srx_devices')
         #primary_devices = findout_primary_devices(device_information_values)

         #
         primaryAll_info = exact_findout('juniperSrx_hastatus',{"failover" : "primary"})
         primaryAccessIp = []
         for _dictValue_ in primaryAll_info:
            #_value_ = str(_dictValue_[u'apiaccessip'])
            _value_ = "%(_hostName_)s::%(_ipaddr_)s" % {'_hostName_': str(_dictValue_[u'hostname']), '_ipaddr_':str(_dictValue_[u'apiaccessip'])}
            if _value_ not in primaryAccessIp:
              primaryAccessIp.append(_value_)


         # delete old files : USER_VAR_POLICIES
         except_filenames = ['readme.txt']
         for _filename_ in os.listdir(USER_VAR_POLICIES):
            if _filename_ not in except_filenames: 
              _filefull_ = USER_VAR_POLICIES + _filename_
              os.popen('rm -rf %(_filefull_)s' % {'_filefull_':_filefull_})
         # 
         except_filenames = ['readme.txt']
         for _filename_ in os.listdir(USER_VAR_NAT):
            if _filename_ not in except_filenames:
              _filefull_ = USER_VAR_NAT + _filename_
              os.popen('rm -rf %(_filefull_)s' % {'_filefull_':_filefull_}) 

         #
         except_filenames = ['readme.txt']
         for _filename_ in os.listdir(USER_VAR_ADDRESSBOOK):
            if _filename_ not in except_filenames:
              _filefull_ = USER_VAR_ADDRESSBOOK + _filename_
              os.popen('rm -rf %(_filefull_)s' % {'_filefull_':_filefull_})
          

         # queue generation
         #processing_queues_list = []
         #for _primaryip_ in primary_devices:
         #for _primaryip_ in primaryAccessIp:
         #   processing_queues_list.append(Queue(maxsize=0))

         # run processing to get information
         count = 0
         _processor_list_ = []
         #for _primaryip_ in primary_devices:
         for _primaryip_ in primaryAccessIp:
            #this_processor_queue = processing_queues_list[count]
            #_processor_ = Process(target = export_policy, args = (_primaryip_, secondary_devices[str(_primaryip_)], this_processor_queue,))
            #_processor_ = Process(target = export_policy, args = (_primaryip_, primary_detail_info[str(_primaryip_)], this_processor_queue,))
            #_processor_ = Process(target = export_policy, args = (_primaryip_, this_processor_queue,))
            _processor_ = Process(target = export_policy, args = (_primaryip_,))
            _processor_.start()
            _processor_list_.append(_processor_)
            # for next queue
            count = count + 1
         for _processor_ in _processor_list_:
            _processor_.join()

         # get information from the queue
         #search_result = []
         #for _queue_ in processing_queues_list:
         #   while not _queue_.empty():
         #        search_result.append(_queue_.get())
         #
         #if not len(search_result):
         #  return_object = {
         #       "items":[],
         #       "process_status":"error",
         #       "process_msg":"no devices to export"
         #  }
         #  return Response(json.dumps(return_object))
         #
         search_result = {
              "items":[],
              "process_status":"done",
              "process_msg":"done"
         }
         return Response(json.dumps(search_result))
         #return Response(json.dumps({"items":search_result}))

       else:
         return_object = {
              "items":[],
              "process_status":"error",
              "process_msg":"wrong auth_password"
         }
         return Response(json.dumps(return_object))

     # end of if re.search(r"system", system_property["role"], re.I):
     else:
       return_object = {
              "items":[],
              "process_status":"error",
              "process_msg":"host is not system"
       }
       return Response(json.dumps(return_object))
     


