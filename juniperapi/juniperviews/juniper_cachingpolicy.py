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
from juniperapi.setting import USER_VAR_CHCHES
from juniperapi.setting import system_property


import os,re,copy,json,time,threading,sys
import paramiko
from multiprocessing import Process, Queue, Lock

from shared_function import start_end_parse_from_string as start_end_parse_from_string

class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders its content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)


def _caching_in_dictbox_(_keyname_, _dict_box_, _this_value_, _list_box_):
   if _keyname_ not in _dict_box_.keys():
     _dict_box_[_keyname_] = []
   if _this_value_ not in _dict_box_[_keyname_]:
     _dict_box_[_keyname_].append(_this_value_)
   if _keyname_ not in _list_box_:
     _list_box_.append(_keyname_)
   return _dict_box_, _list_box_ 


def _caching_process_(_pattern_, _string_, _app_proto_, _dict_box_, _this_value_, _list_box_):
   searched_value = re.search(_pattern_, _string_)
   if searched_value:
     _this_range_ = searched_value.group(1).strip()
     if re.match("[0-9]+\-65535", _this_range_) or re.match("[0-9]+\-0", _this_range_):
       _this_range_ = "0-65535"
     _keyname_ = "%(_app_proto_)s/%(_this_range_)s" % {"_this_range_":_this_range_, "_app_proto_":_app_proto_}
     _dict_box_, _list_box_ = _caching_in_dictbox_(_keyname_, _dict_box_, _this_value_, _list_box_)
   return _dict_box_, _list_box_


def _caching_net_process_(_string_list_, _dict_box_, _this_value_, _list_box_):
   for _line_string_ in _string_list_:
      _last_content_ = _line_string_.strip().split()[-1]
      searched_value =  re.search("\/([0-9]+)", _last_content_)
      if searched_value:
        _this_subnet_ = searched_value.group(1).strip()
        if int(_this_subnet_) <= 0:
          _last_content_ = "0.0.0.0/0"
        _dict_box_, _list_box_ = _caching_in_dictbox_(_last_content_, _dict_box_, _this_value_, _list_box_) 
   return _dict_box_, _list_box_



def _put_queue_for_address_(_dict_value_, _devicehostname_, _from_zone_, _to_zone_, _colletion_, this_processor_queue, _keyname_string_):
   for _keyname_ in _dict_value_.keys():
      _subnet_size_ = int(0)
      searched_value = re.search("\/([0-9]+)", _keyname_)
      if searched_value:
        _subnet_size_ = int(searched_value.group(1).strip())
      mongodb_input = {'devicehostname':_devicehostname_, 'from_zone':_from_zone_, 'to_zone':_to_zone_, 'subnet_size':int(_subnet_size_), _keyname_string_:_dict_value_[_keyname_]}
      done_msg = "%(_devicehostname_)s caching!" % {"_devicehostname_":_devicehostname_}
      this_processor_queue.put({"message":done_msg,"process_status":"done","process_done_items":mongodb_input, "collection":_colletion_}
      

def _put_queue_for_service_(_dict_value_, _devicehostname_, _from_zone_, _to_zone_, _colletion_, this_processor_queue, _keyname_string_):
   for _keyname_ in _dict_value_.keys():
      _port_range_ = int(0)
      searched_value = re.search("([0-9]+)\-([0-9]+)")
      if searched_value:
        _port_range_ = int(searched_value.group(2).strip()) - int(searched_value.group(1).strip()) + 1
      mongodb_input = {'devicehostname':_devicehostname_, 'from_zone':_from_zone_, 'to_zone':_to_zone_, 'port_count':int(_port_range_), _keyname_string_:_dict_value_[_keyname_]}
      done_msg = "%(_devicehostname_)s completed!" % {"_devicehostname_":_devicehostname_}
      this_processor_queue.put({"message":done_msg,"process_status":"done","process_done_items":mongodb_input, "collection":_colletion_}
     






      
def caching_policy(_filename_, this_processor_queue):
   
   filename_pattern = "([a-zA-Z0-9\#\-\.\/\_\<\>\-\:\*\[\]]+)_from_([a-zA-Z0-9\#\-\.\/\_\<\>\-\:\*\[\]]+)_to_([a-zA-Z0-9\#\-\.\/\_\<\>\-\:\*\[\]]+)"
   searched_filename = re.search(filename_pattern, _filename_)

   if searched_filename:
     _devicehostname_ = re.sub("#dash#","-",searched_filename.group(1).strip())
     _from_zone_ = searched_filename.group(2).strip()
     _to_zone_ = searched_filename.group(3).strip()
     _this_filepath_ = USER_VAR_POLICIES + _filename_

     f = open(_this_filepath_,'r');
     read_contents = f.readlines()
     f.close()
     
     _source_app_cache_ = {}
     _destination_app_cache_ = {} 
     _action_cache_ = {}
     _source_net_cache_ = {}
     _destination_net_cache_ = {}
     _policytable_cache_ = {}

     for _start_end_pair_ in start_end_parse_from_string(read_contents, "Policy:", "Session log:"):

        _policy_start_ = _start_end_pair_[0]
        _policy_end_ = _start_end_pair_[-1]
        _policy_contents_ = read_contents[_policy_start_:_policy_end_]

        # default parameter values confirmation
        _policy_name_ = ''
        _policy_action_ = ''
        _policy_name_pattern_ = "Policy: ([a-zA-Z0-9\#\-\.\/\_\<\>\-\:\*\[\]]+), action-type: ([a-zA-Z0-9\#\-\.\/\_\<\>\-\:\*\[\]]+),"
        _policy_sequence_ = ''
        _policy_sequence_pattern_ = "Sequence number: ([a-zA-Z0-9\#\-\.\/\_\<\>\-\:\*\[\]]+)"
        _policy_from_zone_ = ''
        _policy_to_zone_ = ''
        _policy_zone_pattern_ = "From zone: ([a-zA-Z0-9\#\-\.\/\_\<\>\-\:\*\[\]]+), To zone: ([a-zA-Z0-9\#\-\.\/\_\<\>\-\:\*\[\]]+)"
        count = 0
        _application_index_ = []
        for _line_string_ in _policy_contents_:
           searched_value = re.search(_policy_name_pattern_, _line_string_)
           if searched_value:
             _policy_name_ = searched_value.group(1).strip()
             _policy_action_ = searched_value.group(2).strip().lower()
           searched_value = re.search(_policy_sequence_pattern_, _line_string_)
           if searched_value:
             _policy_sequence_ = searched_value.group(1).strip()
           searched_value = re.search(_policy_zone_pattern_, _line_string_)
           if searched_value:
             _policy_from_zone_ = searched_value.group(1).strip()
             _policy_to_zone_ = searched_value.group(2).strip()
           searched_value = re.search("Application:", _line_string_)
           if searched_value:
             _application_index_.append(count)
           count = count + 1
        _policy_name_sequence_ = "#".join([_policy_name_, _policy_sequence_])

        # policy table initiation 
        _tmpkeyname_ = _policy_name_sequence_
        _policytable_cache_[_tmpkeyname_] = {}
        _policytable_cache_[_tmpkeyname_]['src'] = []
        _policytable_cache_[_tmpkeyname_]['dst'] = []
        _policytable_cache_[_tmpkeyname_]['srcapp'] = []
        _policytable_cache_[_tmpkeyname_]['dstapp'] = []
        _policytable_cache_[_tmpkeyname_]['action'] = []

        # action caching process
        _action_cache_, _policytable_cache_[_tmpkeyname_]['permit'] = _caching_in_dictbox_(_policy_action_, _action_cache_, _policy_name_sequence_, _policytable_cache_[_tmpkeyname_]['permit'])
        
        # application caching process
        _apllication_count_ = len(_application_index_)
        _application_index_.append(len(_policy_contents_))
        _protocol_pattern_ = "IP protocol: ([a-zA-Z0-9]+),"
        _source_app_pattern_ = "Source port range: \[([0-9]+\-[0-9]+)\]"
        _destination_app_pattern_ = "Destination port range: \[([0-9]+\-[0-9]+)\]"
        for _index_ in range(_apllication_count_):
           _app_start_ = _application_index_[_index_]
           _app_end_ = _application_index_[_index_+1]
           _application_contents_ = _policy_contents_[_app_start_:_app_end_]
           # protocol confirm : tcp, udp, icmp
           for _app_string_ in _application_contents_:
              searched_value = re.search(_protocol_pattern_, _app_string_) 
              if searched_value:
                _app_proto_ = searched_value.group(1).strip().lower()
                break

           if re.search('icmp',_app_proto_):
             _source_app_cache_, _policytable_cache_[_tmpkeyname_]['srcapp'] = _caching_in_dictbox_('icmp', _source_app_cache_, _policy_name_sequence_, _policytable_cache_[_tmpkeyname_]['srcapp'])
             _destination_app_cache_, _policytable_cache_[_tmpkeyname_]['dstapp'] = _caching_in_dictbox_('icmp', _destination_app_cache_, _policy_name_sequence_, _policytable_cache_[_tmpkeyname_]['dstapp'])

           elif re.search('tcp',_app_proto_) or re.search('udp',_app_proto_):
             for _app_string_ in _application_contents_:
                _source_app_cache_, _policytable_cache_[_tmpkeyname_]['srcapp'] = _caching_process_(_source_app_pattern_, _app_string_, _app_proto_, _source_app_cache_, _policy_name_sequence_, _policytable_cache_[_tmpkeyname_]['srcapp'])
                _destination_app_cache_, _policytable_cache_[_tmpkeyname_]['dstapp'] = _caching_process_(_destination_app_pattern_, _app_string_, _app_proto_, _destination_app_cache_, _policy_name_sequence_, _policytable_cache_[_tmpkeyname_]['dstapp'])

           elif re.search('0',_app_proto_):
             for _app_string_ in _application_contents_:
                _app_proto_ = 'tcp'
                _source_app_cache_, _policytable_cache_[_tmpkeyname_]['srcapp'] = _caching_process_(_source_app_pattern_, _app_string_, _app_proto_, _source_app_cache_, _policy_name_sequence_, _policytable_cache_[_tmpkeyname_]['srcapp'])
                _destination_app_cache_, _policytable_cache_[_tmpkeyname_]['dstapp'] = _caching_process_(_destination_app_pattern_, _app_string_, _app_proto_, _destination_app_cache_, _policy_name_sequence_, _policytable_cache_[_tmpkeyname_]['dstapp'])
                _app_proto_ = 'udp'
                _source_app_cache_, _policytable_cache_[_tmpkeyname_]['srcapp'] = _caching_process_(_source_app_pattern_, _app_string_, _app_proto_, _source_app_cache_, _policy_name_sequence_, _policytable_cache_[_tmpkeyname_]['srcapp'])
                _destination_app_cache_, _policytable_cache_[_tmpkeyname_]['dstapp'] = _caching_process_(_destination_app_pattern_, _app_string_, _app_proto_, _destination_app_cache_, _policy_name_sequence_, _policytable_cache_[_tmpkeyname_]['dstapp'])

           else:
             # if there is other protocol which i do not know at this time, it will be created!
             print "application protocol is not defined"

        # source network value caching process
        _sourceaddress_contents_ = start_end_parse_from_string(_policy_contents_, "Source addresses:", "Destination addresses:")
        for _line_string_ in _sourceaddress_contents_:
           _strings_ = _policy_contents_[_line_string_[0]:_line_string_[-1]]
           _source_net_cache_, _policytable_cache_[_tmpkeyname_]['src'] = _caching_net_process_(_strings_, _source_net_cache_, _policy_name_sequence_, _policytable_cache_[_tmpkeyname_]['src'])

        _destinationaddress_contents_ = start_end_parse_from_string(_policy_contents_, "Destination addresses:", "Application:")
        for _line_string_ in _destinationaddress_contents_:
           _strings_ = _policy_contents_[_line_string_[0]:_line_string_[-1]]
           _destination_net_cache_, _policytable_cache_[_tmpkeyname_]['dst'] = _caching_net_process_(_strings_, _destination_net_cache_, _policy_name_sequence_, _policytable_cache_[_tmpkeyname_]['dst'])


     # soure and application 
     _put_queue_for_address_(_source_net_cache_, _devicehostname_, _from_zone_, _to_zone_, 'juniper_srx_element_cache', this_processor_queue, 'source_netip')
     _put_queue_for_address_(_destination_net_cache_, _devicehostname_, _from_zone_, _to_zone_, 'juniper_srx_element_cache', this_processor_queue, 'destination_netip')
     _put_queue_for_service_(_source_app_cache_, _devicehostname_, _from_zone_, _to_zone_, 'juniper_srx_element_cache', this_processor_queue, 'source_app')
     _put_queue_for_service_(_destination_app_cache_, _devicehostname_, _from_zone_, _to_zone_, 'juniper_srx_element_cache', this_processor_queue, 'destination_app')
     # _action_cache_
     mongodb_input = {'devicehostname':_devicehostname_, 'from_zone':_from_zone_, 'to_zone':_to_zone_}
     for _keyname_ in _action_cache_:
       mongodb_input[_keyname_] = _action_cache_[_keyname_]
     done_msg = "%(_devicehostname_)s completed!" % {"_devicehostname_":_devicehostname_}
     this_processor_queue.put({"message":done_msg,"process_status":"done","process_done_items":mongodb_input, "collection":'juniper_srx_element_cache'})
     # policy cache
     for _keyname_ in _policytable_cache_.keys():
        mongodb_input = {
                           'devicehostname':_devicehostname_, 
                           'from_zone':_from_zone_, 
                           'to_zone':_to_zone_, 
                           'policy_name':_policy_name_,
                           'policy_sequence':_policy_sequence_,
                           'src':_policytable_cache_[_keyname_]['src'],
                           'dst':_policytable_cache_[_keyname_]['dst'],
                           'srcapp':_policytable_cache_[_keyname_]['srcapp'],
                           'dstapp':_policytable_cache_[_keyname_]['dstapp'],
                           'action':_policytable_cache_[_keyname_]['action'][-1],
                        }  
        done_msg = "%(_devicehostname_)s completed!" % {"_devicehostname_":_devicehostname_}
        this_processor_queue.put({"message":done_msg,"process_status":"done","process_done_items":mongodb_input, "collection":'juniper_srx_policy_cache'})


     
   
   # thread timeout 
   time.sleep(1)


@api_view(['POST'])
@csrf_exempt
def juniper_cachingpolicy(request,format=None):

   JUNIPER_DEVICELIST_DBFILE = USER_DATABASES_DIR + "devicelist.txt"

   if request.method == 'POST':
     if re.search(r"system", system_property["role"], re.I):
       _input_ = JSONParser().parse(request)
       # confirm input type 
       if type(_input_) != type({}):
         return_object = {"items":[{"message":"input should be object or dictionary!!","process_status":"error"}]}
         return Response(json.dumps(return_object))
       # confirm auth
       if ('auth_key' not in _input_.keys()) and (u'auth_key' not in _input_.keys()):
         return_object = {"items":[{"message":"no authorization!","process_status":"error"}]}
         return Response(json.dumps(return_object))
       # 
       auth_matched = re.match(ENCAP_PASSWORD, _input_['auth_key'])
       if auth_matched:

         policy_files_list = os.listdir(USER_VAR_POLICIES)
         # queue generation
         processing_queues_list = []
         for _filename_ in policy_files_list:
            processing_queues_list.append(Queue(maxsize=0))
         # run processing to get information
         count = 0
         _processor_list_ = []
         for _filename_ in policy_files_list:
            this_processor_queue = processing_queues_list[count]
            _processor_ = Process(target = caching_policy, args = (_filename_, this_processor_queue,))
            _processor_.start()
            _processor_list_.append(_processor_)
            # for next queue
            count = count + 1
         for _processor_ in _processor_list_:
            _processor_.join()   

         return Response(json.dumps({}))
       # end of if auth_matched:
       else:
         return_object = {"items":[{"message":"no authorization!","process_status":"error"}]}
         return Response(json.dumps(return_object))
     # end of if re.search(r"system", system_property["role"], re.I):
     else:
       return_object = {"items":[{"message":"this host has no authorizaition!","process_status":"error"}]}
       return Response(json.dumps(return_object))
     

