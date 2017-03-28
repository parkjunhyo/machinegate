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
from shared_function import insert_dictvalues_into_mongodb as insert_dictvalues_into_mongodb
from shared_function import insert_dictvalues_list_into_mongodb as insert_dictvalues_list_into_mongodb
from shared_function import remove_collection as remove_collection


class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders its content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)


def _list_append_(_list_, _value_):
   if _value_ not in _list_:
     _list_.append(_value_)
   return _list_


def _caching_in_dictbox_(_keyname_, _dict_box_, _this_value_):
   if _keyname_ not in _dict_box_.keys():
     _dict_box_[_keyname_] = []
   _dict_box_[_keyname_] = _list_append_(_dict_box_[_keyname_], _this_value_) 
   return _dict_box_


def _caching_port_process_(_pattern_, _string_, _app_proto_, _dict_box_, _this_value_, _this_list_value_):
   searched_value = re.search(_pattern_, _string_)
   if searched_value:
     _this_range_ = searched_value.group(1).strip()
     if re.match("[0-9]+\-65535", _this_range_) or re.match("[0-9]+\-0", _this_range_):
       _this_range_ = "0-65535"
     _keyname_ = "%(_app_proto_)s/%(_this_range_)s" % {"_this_range_":_this_range_, "_app_proto_":_app_proto_}
     _dict_box_ = _caching_in_dictbox_(_keyname_, _dict_box_, _this_value_)
     _this_list_value_ = _list_append_(_this_list_value_, _keyname_)
   return _dict_box_, _this_list_value_


def _caching_net_process_(_string_list_, _dict_box_, _this_value_, _this_list_value_):
   _last_content_ = 'unkown' 
   for _line_string_ in _string_list_:
      _last_content_ = _line_string_.strip().split()[-1]
      searched_value =  re.search("\/([0-9]+)", _last_content_)
      if searched_value:
        _this_subnet_ = searched_value.group(1).strip()
        if int(_this_subnet_) <= 0:
          _last_content_ = "0.0.0.0/0"
        _dict_box_ = _caching_in_dictbox_(_last_content_, _dict_box_, _this_value_)
        _this_list_value_ = _list_append_(_this_list_value_, _last_content_)
   return _dict_box_, _this_list_value_



def _put_queue_for_address_(_dict_value_, _devicehostname_, _from_zone_, _to_zone_, _colletion_, this_processor_queue, _keyname_string_):
   for _keyname_ in _dict_value_.keys():
      _subnet_size_ = 'unknown'
      searched_value = re.search("\/([0-9]+)", _keyname_)
      if searched_value:
        _subnet_size_ = int(searched_value.group(1).strip())
      if not re.search(str(_subnet_size_), 'unknown'):
        mongodb_input = {'devicehostname':_devicehostname_, 'from_zone':_from_zone_, 'to_zone':_to_zone_, 'subnet_size':int(_subnet_size_), 'values':_dict_value_[_keyname_], 'type':_keyname_string_, 'key':_keyname_}
        insert_dictvalues_into_mongodb(_colletion_, mongodb_input) 
      #
      #done_msg = "%(_devicehostname_)s completed!" % {"_devicehostname_":_devicehostname_}
      #this_processor_queue.put({"message":done_msg,"process_status":"done","process_done_items":mongodb_input, "collection":_colletion_})
      

def _put_queue_for_service_(_dict_value_, _devicehostname_, _from_zone_, _to_zone_, _colletion_, this_processor_queue, _keyname_string_):
   for _keyname_ in _dict_value_.keys():
      # this will be used for icmp
      _port_range_ = int(0)
      searched_value = re.search("([0-9]+)\-([0-9]+)", _keyname_)
      if searched_value:
        _port_range_ = int(searched_value.group(2).strip()) - int(searched_value.group(1).strip()) + 1
      mongodb_input = {'devicehostname':_devicehostname_, 'from_zone':_from_zone_, 'to_zone':_to_zone_, 'port_count':int(_port_range_), 'values':_dict_value_[_keyname_], 'type':_keyname_string_, 'key':_keyname_}
      insert_dictvalues_into_mongodb(_colletion_, mongodb_input)
      #
      #done_msg = "%(_devicehostname_)s completed!" % {"_devicehostname_":_devicehostname_}
      #this_processor_queue.put({"message":done_msg,"process_status":"done","process_done_items":mongodb_input, "collection":_colletion_})
     

      
def caching_policy(_filename_, this_processor_queue):
   
   filename_pattern = "([a-zA-Z0-9\#\-\.\/\_\<\>\-\:\*\[\]]+)_from_([a-zA-Z0-9\#\-\.\/\_\<\>\-\:\*\[\]]+)_to_([a-zA-Z0-9\#\-\.\/\_\<\>\-\:\*\[\]]+)"
   searched_filename = re.search(filename_pattern, _filename_)

   if searched_filename:
     # default parameter get from file name.
     _devicehostname_ = re.sub("#dash#","-",searched_filename.group(1).strip())
     _from_zone_ = searched_filename.group(2).strip()
     _to_zone_ = searched_filename.group(3).strip()

     # 
     _target_msg_ = "[ %(_devicehostname_)s ] from %(_from_zone_)s to %(_to_zone_)s" % {'_devicehostname_':_devicehostname_, '_to_zone_':_to_zone_, '_from_zone_':_from_zone_}
     print "%(_target_msg_)s ... caching!" % {'_target_msg_':_target_msg_}

     # file read
     _this_filepath_ = USER_VAR_POLICIES + _filename_
     f = open(_this_filepath_,'r');
     read_contents = f.readlines()
     f.close()
     
     # the values to get during this processing.
     _src_netip_cache_ = {}
     _dst_netip_cache_ = {}
     _src_port_cache_ = {}
     _dst_port_cache_ = {}
     _action_cache_ = {}
     _rule_cache_ = {} 
 
     # obtain single policy 
     _single_policies_list_ = start_end_parse_from_string(read_contents, "Policy:", "Session log:")
     for _start_end_pair_ in _single_policies_list_:
  

        # obtain single policy start and end point
        _policy_start_ = _start_end_pair_[0]
        _policy_end_ = _start_end_pair_[-1]
        # obtain single policy 
        _policy_contents_ = read_contents[_policy_start_:_policy_end_]

        ############################################################################
        # default values from the policy rule
        ############################################################################
        _policy_name_pattern_ = "Policy: ([a-zA-Z0-9\#\-\.\/\_\<\>\-\:\*\[\]]+), action-type: ([a-zA-Z0-9\#\-\.\/\_\<\>\-\:\*\[\]]+),"
        _policy_sequence_pattern_ = "Sequence number: ([a-zA-Z0-9\#\-\.\/\_\<\>\-\:\*\[\]]+)"
        _policy_zone_pattern_ = "From zone: ([a-zA-Z0-9\#\-\.\/\_\<\>\-\:\*\[\]]+), To zone: ([a-zA-Z0-9\#\-\.\/\_\<\>\-\:\*\[\]]+)"
        _policy_application_pattern_ = "Application:"
        # 
        _policy_name_ = ''
        _policy_action_ = ''
        _policy_sequence_ = ''
        _policy_from_zone_ = ''
        _policy_to_zone_ = ''
        #
        count = int(0)
        _application_index_ = []
        for _line_string_ in _policy_contents_:
           # name pattern
           searched_value = re.search(_policy_name_pattern_, _line_string_)
           if searched_value:
             _policy_name_ = searched_value.group(1).strip()
             _policy_action_ = searched_value.group(2).strip().lower()
           # sequence pattern
           searched_value = re.search(_policy_sequence_pattern_, _line_string_)
           if searched_value:
             _policy_sequence_ = searched_value.group(1).strip()
           # zone pattern
           searched_value = re.search(_policy_zone_pattern_, _line_string_)
           if searched_value:
             _policy_from_zone_ = searched_value.group(1).strip()
             _policy_to_zone_ = searched_value.group(2).strip()
           # applicaton pattern
           searched_value = re.search(_policy_application_pattern_, _line_string_)
           if searched_value:
             _application_index_.append(count)
           # line counter for index.
           count = count + 1
        # unique name : policy name + sequence number
        _policy_name_sequence_ = "#".join([_policy_name_, _policy_sequence_])

        ############################################################################
        # _rule_cache_ will be initiated 
        ############################################################################
        _rule_cache_[_policy_name_sequence_] = {}
        _rule_cache_[_policy_name_sequence_]['src_netip'] = []
        _rule_cache_[_policy_name_sequence_]['dst_netip'] = []
        _rule_cache_[_policy_name_sequence_]['src_port'] = []
        _rule_cache_[_policy_name_sequence_]['dst_port'] = []
        _rule_cache_[_policy_name_sequence_]['action'] = _policy_action_

        # action caching process
        _action_cache_ = _caching_in_dictbox_(_policy_action_, _action_cache_, _policy_name_sequence_)

        # application caching process
        _apllication_count_ = len(_application_index_)
        _application_index_.append(len(_policy_contents_))
        #
        _protocol_pattern_ = "IP protocol: ([a-zA-Z0-9]+),"
        _source_app_pattern_ = "Source port range: \[([0-9]+\-[0-9]+)\]"
        _destination_app_pattern_ = "Destination port range: \[([0-9]+\-[0-9]+)\]"
        #
        for _index_ in range(_apllication_count_):
           _app_start_ = _application_index_[_index_]
           _app_end_ = _application_index_[_index_+1]
           _application_contents_ = _policy_contents_[_app_start_:_app_end_]

           # protocol confirm : tcp, udp, icmp
           for _app_string_ in _application_contents_:
              searched_value = re.search(_protocol_pattern_, _app_string_, re.I)
              if searched_value:
                _app_proto_ = searched_value.group(1).strip().lower()
                break

           if re.search('icmp',_app_proto_):
             _src_port_cache_ = _caching_in_dictbox_('icmp', _src_port_cache_, _policy_name_sequence_)
             _dst_port_cache_ = _caching_in_dictbox_('icmp', _dst_port_cache_, _policy_name_sequence_)
             _rule_cache_[_policy_name_sequence_]['src_port'] = _list_append_(_rule_cache_[_policy_name_sequence_]['src_port'], 'icmp')
             _rule_cache_[_policy_name_sequence_]['dst_port'] = _list_append_(_rule_cache_[_policy_name_sequence_]['dst_port'], 'icmp')

           # 6 : tcp
           # 17 : udp
           elif re.search('tcp',_app_proto_) or re.search('udp',_app_proto_) or re.search('6',_app_proto_) or re.search('17',_app_proto_):
             for _app_string_ in _application_contents_:
                _src_port_cache_, _rule_cache_[_policy_name_sequence_]['src_port'] = _caching_port_process_(_source_app_pattern_, _app_string_, _app_proto_, _src_port_cache_, _policy_name_sequence_, _rule_cache_[_policy_name_sequence_]['src_port'])
                _dst_port_cache_, _rule_cache_[_policy_name_sequence_]['dst_port'] = _caching_port_process_(_destination_app_pattern_, _app_string_, _app_proto_, _dst_port_cache_, _policy_name_sequence_, _rule_cache_[_policy_name_sequence_]['dst_port'])

           # esp : Encap Security Payload
           # ah : Authentication Header
           # 89 : OSPFIGP
           elif re.search('esp',_app_proto_) or re.search('ah',_app_proto_) or re.search('89',_app_proto_):
             for _app_string_ in _application_contents_:
                _src_port_cache_, _rule_cache_[_policy_name_sequence_]['src_port'] = _caching_port_process_(_source_app_pattern_, _app_string_, _app_proto_, _src_port_cache_, _policy_name_sequence_, _rule_cache_[_policy_name_sequence_]['src_port'])
                _dst_port_cache_, _rule_cache_[_policy_name_sequence_]['dst_port'] = _caching_port_process_(_destination_app_pattern_, _app_string_, _app_proto_, _dst_port_cache_, _policy_name_sequence_, _rule_cache_[_policy_name_sequence_]['dst_port'])     
                
           elif re.search('0',_app_proto_):
             for _app_string_ in _application_contents_:
                _src_port_cache_, _rule_cache_[_policy_name_sequence_]['src_port'] = _caching_port_process_(_source_app_pattern_, _app_string_, 'tcp', _src_port_cache_, _policy_name_sequence_, _rule_cache_[_policy_name_sequence_]['src_port'])
                _dst_port_cache_, _rule_cache_[_policy_name_sequence_]['dst_port'] = _caching_port_process_(_destination_app_pattern_, _app_string_, 'udp', _dst_port_cache_, _policy_name_sequence_, _rule_cache_[_policy_name_sequence_]['dst_port'])
                _src_port_cache_, _rule_cache_[_policy_name_sequence_]['src_port'] = _caching_port_process_(_source_app_pattern_, _app_string_, 'tcp', _src_port_cache_, _policy_name_sequence_, _rule_cache_[_policy_name_sequence_]['src_port'])
                _dst_port_cache_, _rule_cache_[_policy_name_sequence_]['dst_port'] = _caching_port_process_(_destination_app_pattern_, _app_string_, 'udp', _dst_port_cache_, _policy_name_sequence_, _rule_cache_[_policy_name_sequence_]['dst_port'])

           else:
             # if there is other protocol which i do not know at this time, it will be created!
             print "application protocol is not defined"

        ############################################################################
        # source network value caching process
        ############################################################################
        _sourceaddress_contents_ = start_end_parse_from_string(_policy_contents_, "Source addresses:", "Destination addresses:")
        for _line_string_ in _sourceaddress_contents_:
           _strings_ = _policy_contents_[_line_string_[0]:_line_string_[-1]]
           _src_netip_cache_, _rule_cache_[_policy_name_sequence_]['src_netip'] = _caching_net_process_(_strings_, _src_netip_cache_, _policy_name_sequence_, _rule_cache_[_policy_name_sequence_]['src_netip'])

        ############################################################################
        # destination network value caching process
        ############################################################################
        _destinationaddress_contents_ = start_end_parse_from_string(_policy_contents_, "Destination addresses:", "Application:")
        for _line_string_ in _destinationaddress_contents_:
           _strings_ = _policy_contents_[_line_string_[0]:_line_string_[-1]]
           _dst_netip_cache_, _rule_cache_[_policy_name_sequence_]['dst_netip'] = _caching_net_process_(_strings_, _dst_netip_cache_, _policy_name_sequence_, _rule_cache_[_policy_name_sequence_]['dst_netip']) 

     ##########################################################
     # end of for _start_end_pair_ in _single_policies_list_:
     ##########################################################

     ## soure, destaintion, application and aciton caching
     _put_queue_for_address_(_src_netip_cache_, _devicehostname_, _from_zone_, _to_zone_, 'juniper_srx_element_cache', this_processor_queue, 'src_netip')
     _put_queue_for_address_(_dst_netip_cache_, _devicehostname_, _from_zone_, _to_zone_, 'juniper_srx_element_cache', this_processor_queue, 'dst_netip')
     _put_queue_for_service_(_src_port_cache_, _devicehostname_, _from_zone_, _to_zone_, 'juniper_srx_element_cache', this_processor_queue, 'src_port')
     _put_queue_for_service_(_dst_port_cache_, _devicehostname_, _from_zone_, _to_zone_, 'juniper_srx_element_cache', this_processor_queue, 'dst_port')
     
     _temp_mongoin_list_ = []
     mongodb_input = {'devicehostname':_devicehostname_, 'from_zone':_from_zone_, 'to_zone':_to_zone_}
     for _keyname_ in _action_cache_:
        mongodb_input['key'] = _keyname_
        mongodb_input['values'] = _action_cache_[_keyname_]
        _temp_mongoin_list_.append(mongodb_input)  
        #insert_dictvalues_into_mongodb('juniper_srx_element_cache', mongodb_input)
     insert_dictvalues_list_into_mongodb('juniper_srx_element_cache', _temp_mongoin_list_)   
        
     # policy cache
     _temp_mongoin_list_ = []
     for _keyname_ in _rule_cache_.keys():
        mongodb_input = {
                           'devicehostname':_devicehostname_, 
                           'from_zone':_from_zone_, 
                           'to_zone':_to_zone_, 
                           'src_netip':_rule_cache_[_keyname_]['src_netip'],
                           'dst_netip':_rule_cache_[_keyname_]['dst_netip'],
                           'src_port':_rule_cache_[_keyname_]['src_port'],
                           'dst_port':_rule_cache_[_keyname_]['dst_port'],
                           'action':_rule_cache_[_keyname_]['action'],
                           'unique_name':_keyname_
                         }
        _temp_mongoin_list_.append(mongodb_input)
        #insert_dictvalues_into_mongodb('juniper_srx_rule_table_cache', mongodb_input)
     insert_dictvalues_list_into_mongodb('juniper_srx_rule_table_cache', _temp_mongoin_list_)   
     #
     _completed_msg_ = "%(_target_msg_)s  ... cached!" % {'_target_msg_':_target_msg_}
     print _completed_msg_
     this_processor_queue.put({"message":_completed_msg_,"process_status":"done"})

   # thread timeout 
   time.sleep(1)


@api_view(['POST'])
@csrf_exempt
def juniper_cachingpolicy(request,format=None):

   #JUNIPER_DEVICELIST_DBFILE = USER_DATABASES_DIR + "devicelist.txt"

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
         #
         remove_collection('juniper_srx_element_cache')
         remove_collection('juniper_srx_rule_table_cache')
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
         # get information from the queue
         search_result = []
         for _queue_ in processing_queues_list:
            while not _queue_.empty():
                 _get_values_ = _queue_.get()
                 search_result.append(_get_values_)
         # get information from the queue
         if not len(search_result):
           remove_collection('juniper_srx_element_cache')
           remove_collection('juniper_srx_rule_table_cache')
           search_result = [{"message":"caching information cleared!","process_status":"error"}]
         return Response(json.dumps({"items":search_result}))
       # end of if auth_matched:
       else:
         return_object = {"items":[{"message":"no authorization!","process_status":"error"}]}
         return Response(json.dumps(return_object))
     # end of if re.search(r"system", system_property["role"], re.I):
     else:
       return_object = {"items":[{"message":"this host has no authorizaition!","process_status":"error"}]}
       return Response(json.dumps(return_object))
     

