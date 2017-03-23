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
from juniperapi.setting import USER_VAR_CHCHES
from juniperapi.setting import PYTHON_MULTI_PROCESS
from juniperapi.setting import PYTHON_MULTI_THREAD
from juniperapi.setting import system_property

import os,re,copy,json,time,threading,sys,random
import paramiko
from netaddr import *
from multiprocessing import Process, Queue, Lock

from shared_function import obtainjson_from_mongodb as obtainjson_from_mongodb
from shared_function import exact_findout as exact_findout
from shared_function import findout_primary_devices as findout_primary_devices
from shared_function import exact_findout as exact_findout


class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders its content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)


def procesing_searchingzone(_netip_, routing_info_per_devicehost, this_processor_queue):
   #
   _this_subnet_ = int(str(_netip_).split('/')[-1])
   _this_IPNetwork = IPNetwork(str(_netip_))
   # search and find default routing and zone 
   _default_gateway_zone_ = ''
   for _dictvalues_ in routing_info_per_devicehost:
      if re.search('0.0.0.0/0', _dictvalues_[u'routing_address'], re.I):
        _default_gateway_zone_ = _dictvalues_[u'zonename']
        break
   #
   logested_matched_routing = []
   #
   matched_routing = {}
   for _dictvalues_ in routing_info_per_devicehost:
      _in_subnet_ = int(str(_dictvalues_[u'routing_address']).split('/')[-1])
      if not re.search('0.0.0.0/0', str(_dictvalues_[u'routing_address'])):
        if _this_IPNetwork in IPNetwork(str(_dictvalues_[u'routing_address'])):
          if _in_subnet_ not in matched_routing.keys():
            matched_routing[_in_subnet_] = []
          matched_routing[_in_subnet_].append(_dictvalues_)
   #
   _subnets_list_ = matched_routing.keys()
   _subnets_list_.sort()
   if len(_subnets_list_):
     _subnet_max_ = _subnets_list_[-1]
     for _dictvalues_ in matched_routing[_subnet_max_]:
        _unique_string_ = '#unique#'.join([str(_netip_), str(_dictvalues_[u'devicehostname']), str(_dictvalues_[u'apiaccessip']), str(_dictvalues_[u'zonename']), str(_dictvalues_[u'routing_address'])])
        _selected_value_ = {'searching_netip':str(_netip_), 'devicehostname':str(_dictvalues_[u'devicehostname']), 'apiaccessip':str(_dictvalues_[u'apiaccessip']), 'zonename':str(_dictvalues_[u'zonename']), 'routing_address':str(_dictvalues_[u'routing_address']), 'unique_string':_unique_string_}
        logested_matched_routing.append(_selected_value_)
   #
   matched_routing = {}
   for _dictvalues_ in routing_info_per_devicehost:
      _in_subnet_ = int(str(_dictvalues_[u'routing_address']).split('/')[-1])
      if not re.search('0.0.0.0/0', str(_dictvalues_[u'routing_address'])):
        if IPNetwork(str(_dictvalues_[u'routing_address'])) in _this_IPNetwork:
          _unique_string_ = '#unique#'.join([str(_dictvalues_[u'routing_address']), str(_dictvalues_[u'devicehostname']), str(_dictvalues_[u'apiaccessip']), str(_dictvalues_[u'zonename']), str(_dictvalues_[u'routing_address'])])
          _selected_value_ = {'searching_netip':str(_dictvalues_[u'routing_address']), 'devicehostname':str(_dictvalues_[u'devicehostname']), 'apiaccessip':str(_dictvalues_[u'apiaccessip']), 'zonename':str(_dictvalues_[u'zonename']), 'routing_address':str(_dictvalues_[u'routing_address']), 'unique_string':_unique_string_}
          _added_status_ = True
          for _dict_ in logested_matched_routing:
             if re.search(_unique_string_, _dict_['unique_string']):
               _added_status_ = False 
          if _added_status_:
            logested_matched_routing.append(_selected_value_)
   #
   searched_routing_list = {}
   for _dictvalues_ in logested_matched_routing:
      _in_subnet_ = int(_dictvalues_['searching_netip'].split('/')[-1])
      if _in_subnet_ not in searched_routing_list.keys():
        searched_routing_list[_in_subnet_] = []
      searched_routing_list[_in_subnet_].append(_dictvalues_)
   _subnets_list_ = searched_routing_list.keys()
   _subnets_list_.sort()
   #
   eleminated_routing_list = []
   for _index_ in range(len(_subnets_list_)):
      if _index_ < len(_subnets_list_) - 1: 
        _subnet_max_ = _subnets_list_[_index_]
        _subnet_min_list_ = _subnets_list_[_index_+1:]
        for _dictvalues_ in searched_routing_list[_subnet_max_]:
           _coverage_status_ = True
           for _subnet_min_ in _subnet_min_list_:
              _subneted_IPNetwork_ = list(IPNetwork(_dictvalues_['searching_netip']).subnet(_subnet_min_))
              if len(_subneted_IPNetwork_) <= len(searched_routing_list[_subnet_min_]):
                for _compdict_ in searched_routing_list[_subnet_min_]:
                   if IPNetwork(_compdict_['searching_netip']) in _subneted_IPNetwork_:
                     _subneted_IPNetwork_.remove(IPNetwork(_compdict_['searching_netip']))
                if not len(_subneted_IPNetwork_):
                  _coverage_status_ = False
           if _coverage_status_:
             eleminated_routing_list.append(_dictvalues_)
      elif _index_ == len(_subnets_list_) - 1: 
        _subnet_max_ = _subnets_list_[_index_]
        for _dictvalues_ in searched_routing_list[_subnet_max_]:
           eleminated_routing_list.append(_dictvalues_)
   #
   if len(eleminated_routing_list):
     for _dictvalues_ in eleminated_routing_list:
        if 'unique_string' in _dictvalues_.keys():
          del _dictvalues_['unique_string']
        this_processor_queue.put(_dictvalues_)
   else:
     if _default_gateway_zone_:
       this_processor_queue.put({'searching_netip':str(_netip_), 'devicehostname':str(_dictvalues_[u'devicehostname']), 'apiaccessip':str(_dictvalues_[u'apiaccessip']), 'zonename':str(_default_gateway_zone_)}) 
   #
   time.sleep(1)

def _recursive_instersection_(_comp_list_to_match_):
   _comp_list_to_match_values_ = _comp_list_to_match_.values()
   start_list = _comp_list_to_match_values_[0]
   for _index_ in range(len(_comp_list_to_match_values_) - 1):
      _this_index_ = _index_ + 1
      start_list = list(set(start_list).intersection(_comp_list_to_match_values_[_this_index_]))
   return start_list

def _update_unique_per_zonematching_(_from_zone_, _to_zone_, _values_, _unique_per_zonematching_, _matchstatus_):
   _fromto_keyname_ = str(_from_zone_) + '_' + str(_to_zone_)
   for _unique_nameseq_ in _values_:
      if str(_unique_nameseq_) not in _unique_per_zonematching_[_matchstatus_][_fromto_keyname_]:
        _unique_per_zonematching_[_matchstatus_][_fromto_keyname_].append(str(_unique_nameseq_))
   return _unique_per_zonematching_


def _range_list_(_string_):
   _basic_search_ = re.search('([0-9]+)\-([0-9]+)', _string_)
   if _basic_search_:
     _range_start_ = int(_basic_search_.group(1).strip())
     _range_end_ = int(_basic_search_.group(2).strip())
     _range_length_ = _range_end_ - _range_start_ + 1
     _basic_ = list(map(lambda x:x+_range_start_, range(_range_length_)))
   else:
     # other procotocol such as 'icmp'
     if re.search('icmp', _string_):
       _basic_ = [0] 
   return _basic_

def _inersection_by_from_to_zones_(_tempdict_box_, _this_result_out_, unique_per_zonematching, _fromto_keyname_):
   _tempdict_box_['prefectmatch'] = list(set(_this_result_out_['prefectmatch']).intersection(unique_per_zonematching['prefectmatch'][_fromto_keyname_]))
   _tempdict_box_['includedmatch'] = list(set(_this_result_out_['includedmatch']).intersection(unique_per_zonematching['includedmatch'][_fromto_keyname_]))
   _tempdict_box_['partialmatch'] = list(set(_this_result_out_['partialmatch']).intersection(unique_per_zonematching['partialmatch'][_fromto_keyname_]))
   return _tempdict_box_


def procesing_cachelookup(_dictvalue_, this_processor_queue):
   #
   _essence_items_ = ['src_netip', 'dst_netip', 'src_port', 'dst_port']
   _lookup_keynames_ = _dictvalue_.keys()
   _maybe_any_keynames_ = list(set(_essence_items_) - set(_lookup_keynames_))
   
   # zone (from, to) and hostname is basic formation to search
   search_key = {}
   if ('src_netip' in _lookup_keynames_) and ('dst_netip' in _lookup_keynames_):
     search_key["devicehostname"] = str(_dictvalue_['src_netip']['devicehostname'])
     search_key["from_zone"] = str(_dictvalue_['src_netip']['zonename'])
     search_key["to_zone"] = str(_dictvalue_['dst_netip']['zonename'])
   elif ('src_netip' in _lookup_keynames_) and ('dst_netip' not in _lookup_keynames_):
     search_key["devicehostname"] = str(_dictvalue_['src_netip']['devicehostname'])
     search_key["from_zone"] = str(_dictvalue_['src_netip']['zonename'])
   elif ('src_netip' not in _lookup_keynames_) and ('dst_netip' in _lookup_keynames_):
     search_key["devicehostname"] = str(_dictvalue_['dst_netip']['devicehostname'])
     search_key["to_zone"] = str(_dictvalue_['dst_netip']['zonename'])

   # this value will be used for recover any parameters
   return_basic_dictvalue_form = copy.copy(search_key)
   #
   for _ess_keyname_ in _essence_items_:
      if _ess_keyname_ in _lookup_keynames_:
        if re.search('src_netip', _ess_keyname_) or re.search('dst_netip', _ess_keyname_):
          return_basic_dictvalue_form[_ess_keyname_] = _dictvalue_[_ess_keyname_]['searching_netip']
        else:
          return_basic_dictvalue_form[_ess_keyname_] = _dictvalue_[_ess_keyname_]

   #
   _zonenames_in_thisdeivce_ = []
   for _find_dict_ in exact_findout('juniper_srx_devices', {'devicehostname':return_basic_dictvalue_form['devicehostname']}):
      for _find_zonename_ in _find_dict_['zonesinfo'].keys():
         if str(_find_zonename_) not in _zonenames_in_thisdeivce_:
           _zonenames_in_thisdeivce_.append(str(_find_zonename_))

   # information gathering box 
   unique_per_zonematching = {}
   unique_per_zonematching['prefectmatch'] = {}
   unique_per_zonematching['includedmatch'] = {}
   unique_per_zonematching['partialmatch'] = {}
   for _tmp_from_ in _zonenames_in_thisdeivce_:
      for _tmp_to_ in _zonenames_in_thisdeivce_:
         if not re.search(_tmp_from_, _tmp_to_):
           _fromto_keyname_ = _tmp_from_ + '_' + _tmp_to_
           unique_per_zonematching['prefectmatch'][_fromto_keyname_] = []
           unique_per_zonematching['includedmatch'][_fromto_keyname_] = []
           unique_per_zonematching['partialmatch'][_fromto_keyname_] = []

   # this values is used for 'prefectmatch', 'includedmatch' and 'partialmatch' informations
   _this_result_out_ = {}
   
   ###################  perfect match processing 
   _comp_list_to_match_ = {}
   for _keyname_ in _lookup_keynames_:
      #
      copied_search_key = copy.copy(search_key)
      copied_search_key['type'] = str(_keyname_)
      #
      if _keyname_ not in _comp_list_to_match_:
        _comp_list_to_match_[_keyname_] = []
      # searching into the database for src_netip and dst_netip
      if re.search('src_netip', str(_keyname_)) or re.search('dst_netip', str(_keyname_)):
        copied_search_key['key'] = str(_dictvalue_[_keyname_]['searching_netip'])
        copied_search_key['subnet_size'] = int(str(_dictvalue_[_keyname_]['searching_netip']).split('/')[-1])
        # searching 
        _searched_result_ = exact_findout('juniper_srx_element_cache', copied_search_key)
        if _searched_result_:
          for _indict_ in _searched_result_:
             _comp_list_to_match_[_keyname_] = _comp_list_to_match_[_keyname_] + _indict_[u'values'] 
             unique_per_zonematching = _update_unique_per_zonematching_(_indict_[u'from_zone'], _indict_[u'to_zone'], _indict_[u'values'], unique_per_zonematching, 'prefectmatch')

      # searching into the database for src_port and dst_port
      elif re.search('src_port', str(_keyname_)) or re.search('dst_port', str(_keyname_)): 
        searched_portvalues = re.search('([a-zA-Z0-9]+)\/([0-9]+)\-([0-9]+)', str(_dictvalue_[_keyname_]))
        if searched_portvalues:
          _protocol_ = searched_portvalues.group(1).strip()
          # case : icmp
          if re.search('icmp', _protocol_):
            copied_search_key['key'] = 'icmp'
            copied_search_key['port_count'] = int(0)
            # searching
            _searched_result_ = exact_findout('juniper_srx_element_cache', copied_search_key)
            if _searched_result_:
              for _indict_ in _searched_result_:
                 _comp_list_to_match_[_keyname_] = _comp_list_to_match_[_keyname_] + _indict_[u'values']
                 unique_per_zonematching = _update_unique_per_zonematching_(_indict_[u'from_zone'], _indict_[u'to_zone'], _indict_[u'values'], unique_per_zonematching, 'prefectmatch') 

          # case : tcp, udp
          elif re.search('tcp', _protocol_) or re.search('udp', _protocol_):
            copied_search_key['key'] = str(_dictvalue_[_keyname_])
            copied_search_key['port_count'] = int(searched_portvalues.group(3).strip()) - int(searched_portvalues.group(2).strip()) + 1
            # searching
            _searched_result_ = exact_findout('juniper_srx_element_cache', copied_search_key)
            if _searched_result_:
              for _indict_ in _searched_result_:
                 _comp_list_to_match_[_keyname_] = _comp_list_to_match_[_keyname_] + _indict_[u'values']
                 unique_per_zonematching = _update_unique_per_zonematching_(_indict_[u'from_zone'], _indict_[u'to_zone'], _indict_[u'values'], unique_per_zonematching, 'prefectmatch')

          # case : other
          else:
            print 'other protocol is defined, fail to search in database! - 1'

   # intersection and 'perfect match' define
   _this_result_out_['prefectmatch'] = _recursive_instersection_(_comp_list_to_match_)
      
   ################### included match processing
   for _keyname_ in _lookup_keynames_:
      copied_search_key = copy.copy(search_key)
      copied_search_key['type'] = _keyname_
      # searching into the database for src_netip and dst_netip
      if re.search('src_netip', str(_keyname_)) or re.search('dst_netip', str(_keyname_)):
        copied_search_key['subnet_size'] = { '$lt':int(str(_dictvalue_[_keyname_]['searching_netip']).split('/')[-1]) }
        # searching
        _searched_result_ = exact_findout('juniper_srx_element_cache', copied_search_key)
        if _searched_result_:
          _basic_ = IPNetwork(unicode(_dictvalue_[_keyname_]['searching_netip']))
          for _indict_ in _searched_result_:
             if _basic_ in IPNetwork(unicode(_indict_[u'key'])):
               _comp_list_to_match_[_keyname_] = _comp_list_to_match_[_keyname_] + _indict_[u'values']
               unique_per_zonematching = _update_unique_per_zonematching_(_indict_[u'from_zone'], _indict_[u'to_zone'], _indict_[u'values'], unique_per_zonematching, 'includedmatch')

      # searching into the database for src_port and dst_port
      elif re.search('src_port', str(_keyname_)) or re.search('dst_port', str(_keyname_)):
        searched_portvalues = re.search('([a-zA-Z0-9]+)\/([0-9]+)\-([0-9]+)', str(_dictvalue_[_keyname_]))
        if searched_portvalues:
          _protocol_ = searched_portvalues.group(1).strip()
          # case : icmp
          if re.search('icmp', _protocol_):
            copied_search_key['key'] = 'icmp'
            copied_search_key['port_count'] = { '$gt':int(0) }
            # searching
            _searched_result_ = exact_findout('juniper_srx_element_cache', copied_search_key)
            if _searched_result_:
              for _indict_ in _searched_result_:
                 _comp_list_to_match_[_keyname_] = _comp_list_to_match_[_keyname_] + _indict_[u'values']
                 unique_per_zonematching = _update_unique_per_zonematching_(_indict_[u'from_zone'], _indict_[u'to_zone'], _indict_[u'values'], unique_per_zonematching, 'includedmatch')

          # case : tcp, udp 
          elif re.search('tcp', _protocol_) or re.search('udp', _protocol_):
            copied_search_key['port_count'] = { '$gt':int(searched_portvalues.group(3).strip()) - int(searched_portvalues.group(2).strip()) + 1 }
            # searching
            _searched_result_ = exact_findout('juniper_srx_element_cache', copied_search_key)
            if _searched_result_:
              _basic_ = _range_list_(str(_dictvalue_[_keyname_]))
              _set_basic_ = set(_basic_)
              for _indict_ in _searched_result_:
                 _indict_rangelist_ = _range_list_(str(_indict_[u"key"]))
                 _intersection_ = list(_set_basic_.intersection(_indict_rangelist_))
                 if _intersection_ == _basic_:
                   _comp_list_to_match_[_keyname_] = _comp_list_to_match_[_keyname_] + _indict_[u'values']
                   unique_per_zonematching = _update_unique_per_zonematching_(_indict_[u'from_zone'], _indict_[u'to_zone'], _indict_[u'values'], unique_per_zonematching, 'includedmatch')

          # case : other 
          else:
            print 'other protocol is defined, fail to search in database! - 2'

   # intersection and 'include match' define
   _this_result_out_['includedmatch'] = list(set(_recursive_instersection_(_comp_list_to_match_)) - set(_this_result_out_['prefectmatch']))

   ################### partial match process
   for _keyname_ in _lookup_keynames_:
      copied_search_key = copy.copy(search_key)
      copied_search_key['type'] = _keyname_
      # searching into the database for src_netip and dst_netip
      if re.search('src_netip', str(_keyname_)) or re.search('dst_netip', str(_keyname_)):
        copied_search_key['subnet_size'] = { '$gt':int(str(_dictvalue_[_keyname_]['searching_netip']).split('/')[-1]) }
        # searching
        _searched_result_ = exact_findout('juniper_srx_element_cache', copied_search_key)
        if _searched_result_:
          _basic_ = IPNetwork(unicode(_dictvalue_[_keyname_]['searching_netip']))
          for _indict_ in _searched_result_:
             if IPNetwork(unicode(_indict_[u'key'])) in _basic_:
               _comp_list_to_match_[_keyname_] = _comp_list_to_match_[_keyname_] + _indict_[u'values']
               unique_per_zonematching = _update_unique_per_zonematching_(_indict_[u'from_zone'], _indict_[u'to_zone'], _indict_[u'values'], unique_per_zonematching, 'partialmatch')
               #

      # searching into the database for src_port and dst_port
      elif re.search('src_port', str(_keyname_)) or re.search('dst_port', str(_keyname_)):
        searched_portvalues = re.search('([a-zA-Z0-9]+)\/([0-9]+)\-([0-9]+)', str(_dictvalue_[_keyname_]))
        if searched_portvalues:
          _protocol_ = searched_portvalues.group(1).strip()
          # case : icmp
          if re.search('icmp', _protocol_):
            copied_search_key['key'] = 'icmp'
            copied_search_key['port_count'] = { '$lt':int(0) }
            # searching
            _searched_result_ = exact_findout('juniper_srx_element_cache', copied_search_key)
            if _searched_result_:
              for _indict_ in _searched_result_:
                 _comp_list_to_match_[_keyname_] = _comp_list_to_match_[_keyname_] + _indict_[u'values']
                 unique_per_zonematching = _update_unique_per_zonematching_(_indict_[u'from_zone'], _indict_[u'to_zone'], _indict_[u'values'], unique_per_zonematching, 'partialmatch')

          # case : tcp, udp
          elif re.search('tcp', _protocol_) or re.search('udp', _protocol_):
            copied_search_key['port_count'] = { '$lt':int(searched_portvalues.group(3).strip()) - int(searched_portvalues.group(2).strip()) + 1 }
            # searching
            _searched_result_ = exact_findout('juniper_srx_element_cache', copied_search_key)
            if _searched_result_:
              _basic_ = _range_list_(str(_dictvalue_[_keyname_]))
              _set_basic_ = set(_basic_)
              for _indict_ in _searched_result_:
                 _indict_rangelist_ = _range_list_(str(_indict_[u"key"]))
                 _intersection_ = list(_set_basic_.intersection(_indict_rangelist_))
                 if _intersection_ == _indict_rangelist_:
                   _comp_list_to_match_[_keyname_] = _comp_list_to_match_[_keyname_] + _indict_[u'values']
                   unique_per_zonematching = _update_unique_per_zonematching_(_indict_[u'from_zone'], _indict_[u'to_zone'], _indict_[u'values'], unique_per_zonematching, 'partialmatch')

          # case : other
          else:
            print 'other protocol is defined, fail to search in database! - 3'
   #
   _this_result_out_['partialmatch'] = list(set(_recursive_instersection_(_comp_list_to_match_)) - set(_this_result_out_['includedmatch']) - set(_this_result_out_['prefectmatch']))


   #
   # recovery processing for any input valuse : port recovery
   for _maybe_keyname_ in _maybe_any_keynames_:
      if re.search('src_port', _maybe_keyname_) or re.search('dst_port', _maybe_keyname_): 
        return_basic_dictvalue_form[_maybe_keyname_] = '0/0-0'

   if ('src_netip' in _maybe_any_keynames_) or ('dst_netip' in _maybe_any_keynames_):
     for _maybe_keyname_ in _maybe_any_keynames_:
        #_tempdict_box_ = copy.copy(return_basic_dictvalue_form)
        if re.search('src_netip', _maybe_keyname_):
          for _rcv_zone_ in _zonenames_in_thisdeivce_:
             _tempdict_box_ = copy.copy(return_basic_dictvalue_form)
             if not re.search(_tempdict_box_['to_zone'], _rcv_zone_):
               _tempdict_box_['from_zone'] = _rcv_zone_
               _tempdict_box_['src_netip'] = '0.0.0.0/0'
               _fromto_keyname_ = _rcv_zone_ + '_' + _tempdict_box_['to_zone']
               _tempdict_box_ = _inersection_by_from_to_zones_(_tempdict_box_, _this_result_out_, unique_per_zonematching, _fromto_keyname_)
               this_processor_queue.put({"message":"searching done", "process_status":"done", "process_done_item":_tempdict_box_})

        if re.search('dst_netip', _maybe_keyname_): 
          for _rcv_zone_ in _zonenames_in_thisdeivce_:
             _tempdict_box_ = copy.copy(return_basic_dictvalue_form)
             if not re.search(_tempdict_box_['from_zone'], _rcv_zone_):
               _tempdict_box_['to_zone'] = _rcv_zone_
               _tempdict_box_['dst_netip'] = '0.0.0.0/0'
               _fromto_keyname_ = _tempdict_box_['from_zone'] + '_' + _rcv_zone_
               _tempdict_box_ = _inersection_by_from_to_zones_(_tempdict_box_, _this_result_out_, unique_per_zonematching, _fromto_keyname_)
               this_processor_queue.put({"message":"searching done", "process_status":"done", "process_done_item":_tempdict_box_})
   else:
     _tempdict_box_ = copy.copy(return_basic_dictvalue_form)
     _fromto_keyname_ = _tempdict_box_['from_zone'] + '_' + _tempdict_box_['to_zone']
     _tempdict_box_ = _inersection_by_from_to_zones_(_tempdict_box_, _this_result_out_, unique_per_zonematching, _fromto_keyname_)
     this_processor_queue.put({"message":"searching done", "process_status":"done", "process_done_item":_tempdict_box_})
   # 
   time.sleep(1)



   




def _findout_matched_zone_(routing_info_per_devicehost, _netip_, _candi_src_netip_):
   processing_queues_list = []
   for _devicehost_ in routing_info_per_devicehost.keys():
      processing_queues_list.append(Queue(maxsize=0))
   # run processing to get zone based information
   count = 0
   _processor_list_ = []
   for _devicehost_ in routing_info_per_devicehost.keys():
      this_processor_queue = processing_queues_list[count]
      _processor_ = Process(target = procesing_searchingzone, args = (_netip_, routing_info_per_devicehost[_devicehost_], this_processor_queue,))
      _processor_.start()
      _processor_list_.append(_processor_)
      count = count + 1
   #
   for _processor_ in _processor_list_:
      _processor_.join()
   #
   for _queue_ in processing_queues_list:
      while not _queue_.empty():
           _get_values_ = _queue_.get()
           _candi_src_netip_.append(_get_values_)
   return _candi_src_netip_



@api_view(['GET','POST'])
@csrf_exempt
def juniper_searchpolicy(request,format=None):

   #global tatalsearched_values, threadlock_key
   #threadlock_key = threading.Lock()
   #tatalsearched_values = []



   # get method
   if request.method == 'GET':
     parameter_from = request.query_params.dict()
     _keyname_pattern_ = "([a-zA-Z0-9\-\.\/\_\<\>\-\:\*]*)_from_([a-zA-Z0-9\-\.\/\_\<\>\-\:\*]*)_to_([a-zA-Z0-9\-\.\/\_\<\>\-\:\*]*)"
     if u'devicehostname' not in parameter_from:
       hostname_list = []
       for _dictvalues_ in obtainjson_from_mongodb('juniper_srx_rule_table_cache'):       
          _keyname_ = "%(_host_)s_from_%(_from_)s_to_%(_to_)s" % {'_host_':_dictvalues_[u'devicehostname'], '_from_':_dictvalues_[u'from_zone'], '_to_':_dictvalues_[u'to_zone']}
          if _keyname_ not in hostname_list:
            hostname_list.append(_keyname_) 
       return Response(json.dumps({"items":hostname_list}))
     else:
       parameter_hostname = parameter_from[u'devicehostname'] 
       searched_value = re.search(_keyname_pattern_, str(parameter_hostname))
       if searched_value:
         _target_ = {"devicehostname":searched_value.group(1).strip(),"from_zone":searched_value.group(2).strip(),"to_zone":searched_value.group(3).strip()}
         _obtained_values_ = exact_findout('juniper_srx_rule_table_cache', _target_)
         for _dictvalues_ in _obtained_values_:
            del _dictvalues_[u'_id']
         return Response(json.dumps({"items":_obtained_values_}))



   elif request.method == 'POST':
       if re.search(r"system", system_property["role"], re.I):
         _input_ = JSONParser().parse(request)

         #
         device_information_values = obtainjson_from_mongodb('juniper_srx_devices')
         primary_devices = findout_primary_devices(device_information_values)

         # confirm input type 
         if type(_input_) != type({}):
           return_object = {"items":[{"message":"input should be object or dictionary!!","process_status":"error"}]}
           return Response(json.dumps(return_object))

         # Any Source/Destination, Any service will be eliminated because it is not necessary to search.
         _searching_target_ = []
         if not re.search('0.0.0.0/0', _input_[u'src_netip']):
           _searching_target_.append(u'src_netip') 
         if not re.search('0.0.0.0/0', _input_[u'dst_netip']):
           _searching_target_.append(u'dst_netip')
         if not re.search('0\/[0-9]+\-65535', _input_[u'src_port']) and not re.search('0\/[0-9]+\-0', _input_[u'src_port']):
           _searching_target_.append(u'src_port')
         if not re.search('0\/[0-9]+\-65535', _input_[u'dst_port']) and not re.search('0\/[0-9]+\-0', _input_[u'dst_port']):
           _searching_target_.append(u'dst_port')


         #
         _routing_table_ = obtainjson_from_mongodb('juniper_srx_routingtable')
         if not len(_routing_table_):
           return_object = {"items":[{"message":"there is no routing table registered!!","process_status":"error"}]}
           return Response(json.dumps(return_object))

         # This information is import because it will be used to find out the zone matched.
         routing_info_per_devicehost = {}
         for _dictvalues_ in _routing_table_:
            if _dictvalues_[u"apiaccessip"] in primary_devices:
              _devicehost_ = _dictvalues_[u'devicehostname']
              if _devicehost_ not in routing_info_per_devicehost.keys():
                routing_info_per_devicehost[_devicehost_] = []
              routing_info_per_devicehost[_devicehost_].append(_dictvalues_)

         # findout source zone
         _candi_src_netip_ = []
         if u'src_netip' in _searching_target_:
           _netip_ = _input_[u'src_netip']
           _candi_src_netip_ = _findout_matched_zone_(routing_info_per_devicehost, _netip_, _candi_src_netip_)

         # findout destination zone
         _candi_dst_netip_ = []
         if u'dst_netip' in _searching_target_:
           _netip_ = _input_[u'dst_netip']
           _candi_dst_netip_ = _findout_matched_zone_(routing_info_per_devicehost, _netip_, _candi_dst_netip_)

         # intersection : this is import to decrease the searching time.
         if len(_candi_src_netip_):
           if len(_candi_dst_netip_):
             _candi_comb_ = []
             for _src_dictvalue_ in _candi_src_netip_:
                for _dst_dictvalue_ in _candi_dst_netip_:
                   if re.match(str(_src_dictvalue_['devicehostname']), str(_dst_dictvalue_['devicehostname'])):
                     if not re.match(str(_src_dictvalue_['zonename']), str(_dst_dictvalue_['zonename'])):
                       _candi_comb_.append({'src_netip':_src_dictvalue_ ,'dst_netip':_dst_dictvalue_})
           else:
             _candi_comb_ = []
             for _src_dictvalue_ in _candi_src_netip_:
                _candi_comb_.append({'src_netip':_src_dictvalue_})
         else:
           if len(_candi_dst_netip_):
             _candi_comb_ = []
             for _dst_dictvalue_ in _candi_dst_netip_:
                _candi_comb_.append({'dst_netip':_dst_dictvalue_})
           else:
             return_object = {"items":[{"message":"all any is not allowed!","process_status":"error"}]}
             return Response(json.dumps(return_object))

         # 
         if u'src_port' in _searching_target_:
           for _dictvalue_ in _candi_comb_:
              _dictvalue_['src_port'] = _input_[u'src_port']
         #
         if u'dst_port' in _searching_target_:
           for _dictvalue_ in _candi_comb_:
              _dictvalue_['dst_port'] = _input_[u'dst_port']

         ###################################################################
         # until this, zone was found by the routing table
         ###################################################################
         processing_queues_list = []
         for _dictvalue_ in _candi_comb_:
            processing_queues_list.append(Queue(maxsize=0))
         #
         count = 0
         _processor_list_ = []
         for _dictvalue_ in _candi_comb_:
            this_processor_queue = processing_queues_list[count]
            _processor_ = Process(target = procesing_cachelookup, args = (_dictvalue_, this_processor_queue,))
            _processor_.start()
            _processor_list_.append(_processor_)
            count = count + 1
         for _processor_ in _processor_list_:
            _processor_.join()
         #
         search_result = []
         for _queue_ in processing_queues_list:
            while not _queue_.empty():
                 _get_values_ = _queue_.get()
                 if re.search(_get_values_['process_status'], 'done'):
                   search_result.append(_get_values_['process_done_item'])
           
         #print search_result
         return Response(json.dumps({"items":search_result})) 

       # end of if re.search(r"system", system_property["role"], re.I):
       else:
         return_object = {"items":[{"message":"this host has no authorizaition!","process_status":"error"}]}
         return Response(json.dumps(return_object))

#
######################################################################################
#        # input
#        _input_ = JSONParser().parse(request)
#
#        # cache directory
#        cache_filename = []
#        for _fname_ in os.listdir(USER_VAR_CHCHES):
#           if re.search("cachepolicy_", _fname_.strip(), re.I):
#             if _fname_ not in cache_filename:
#               cache_filename.append(_fname_)
#
#        # get devicelist
#        CURL_command = "curl http://0.0.0.0:"+RUNSERVER_PORT+"/juniper/devicelist/"
#        get_info = os.popen(CURL_command).read().strip()
#        stream = BytesIO(get_info)
#        _routing_dict_ = JSONParser().parse(stream)
#
#        CURL_command = "curl -H \"Accept: application/json\" -X POST -d \'"+json.dumps(_input_)+"\' http://0.0.0.0:"+RUNSERVER_PORT+"/juniper/searchzonefromroute/"
#        get_info = os.popen(CURL_command).read().strip()
#        stream = BytesIO(get_info)
#        data_from_CURL_command = JSONParser().parse(stream)
#######################################################################################

