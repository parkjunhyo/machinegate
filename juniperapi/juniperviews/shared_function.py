#! /usr/bin/env python

import paramiko
import re, time, copy

from juniperapi.setting import USER_NAME
from juniperapi.setting import USER_PASSWORD
from juniperapi.setting import ENCAP_PASSWORD
from juniperapi.setting import paramiko_conf as paramiko_conf

import pymongo
from bson.json_util import dumps, loads
from juniperapi.setting import mongodb as mongodb 


def start_end_parse_from_string(return_lines_string, pattern_start, pattern_end):
   start_end_linenumber_list = []
   line_index_count = 0
   temp_list_box = []
   for _line_string_ in return_lines_string:
      if re.search(pattern_start, _line_string_):
        temp_list_box.append(line_index_count)
      if re.search(pattern_end, _line_string_):
        temp_list_box.append(line_index_count)
        start_end_linenumber_list.append(temp_list_box)
        temp_list_box = []
      line_index_count = line_index_count + 1
   return start_end_linenumber_list


def runssh_clicommand(_ipaddress_, laststring_pattern, runcli_command):
   status_msg_form = "[ %(_ipaddress_)s ] %(runcli_command)s .... %(status)s"
   printout_msg = status_msg_form % {"_ipaddress_":str(_ipaddress_), "runcli_command":str(runcli_command).strip(), "status":"started"}
   print printout_msg
   remote_conn_pre = paramiko.SSHClient()
   remote_conn_pre.set_missing_host_key_policy(paramiko.AutoAddPolicy())
   remote_conn_pre.connect(_ipaddress_, username=USER_NAME, password=USER_PASSWORD, look_for_keys=False, allow_agent=False, timeout=paramiko_conf["connect_timeout"])
   remote_conn = remote_conn_pre.invoke_shell()
   remote_conn.settimeout(paramiko_conf["output_wait_timeout"])
   remote_conn.send(runcli_command)
   string_comb_list = []
   interface_information = []
   wait_count = 0
   processing_finished = 'timeout'
   while True:
      if wait_count < paramiko_conf["max_wait_timeout_count"]:
        try:
           output = remote_conn.recv(2097152)
           if output:
             string_comb_list.append(str(output))
           stringcombination = str("".join(string_comb_list))
           if re.search(laststring_pattern, stringcombination, re.I):
             interface_information = copy.copy(stringcombination.split("\r\n"))
             string_comb_list = []
             processing_finished = 'finished'
             break
        except:
           wait_count = wait_count + 1
           #print "[ %(runcli_command)s ] timeout [ %(wait_count)s ] seconds" % {"runcli_command":runcli_command.strip(), "wait_count":str(wait_count)}
           continue
      else:
        break
   processing_time = wait_count * paramiko_conf["output_wait_timeout"]
   remote_conn.send("exit\n")
   time.sleep(5)
   remote_conn_pre.close()
   _status_message_ = "%(processing_time)s seconds %(processing_finished)s" % {"processing_finished":processing_finished, "processing_time":processing_time}
   printout_msg = status_msg_form % {"_ipaddress_":str(_ipaddress_), "runcli_command":str(runcli_command).strip(), "status":_status_message_}
   print printout_msg
   return interface_information

def sftp_file_download(_ipaddress_, _origin_, _remote_):
   print "[ exporting ] %(_origin_)s file in %(_ipaddress_)s" % {"_ipaddress_":_ipaddress_, "_origin_":_origin_} 
   remote_conn_pre = paramiko.SSHClient()
   remote_conn_pre.set_missing_host_key_policy(paramiko.AutoAddPolicy())
   remote_conn_pre.connect(_ipaddress_, username=USER_NAME, password=USER_PASSWORD, look_for_keys=False, allow_agent=False, timeout=paramiko_conf["connect_timeout"])
   remote_conn_sftp = remote_conn_pre.open_sftp()
   remote_conn_sftp.get(_origin_, _remote_)
   remote_conn_sftp.close()
   remote_conn_pre.close()
   print "[ exported ] %(_remote_)s" % {"_remote_":_remote_}

def exchanged_dot_to_string(_listData_):
   _string_ = dumps(_listData_)
   _exchanged_string_ = re.sub(r"\.", "#dot#", _string_)
   return loads(_exchanged_string_)
   
def recovery_dot_from_string(_string_):
   _exchanged_string_ = re.sub("#dot#", r".", _string_)
   return loads(_exchanged_string_)

def update_dictvalues_into_mongodb(collection_name, inserting_values):
   access_information = {"_dbname_":mongodb["dbname"], "_username_":mongodb["username"], "_password_":mongodb["password"]}
   connection = pymongo.MongoClient(mongodb["ip"],int(mongodb["port"]))
   auth_string = "connection.%(_dbname_)s.authenticate(\"%(_username_)s\",\"%(_password_)s\")" % access_information
   eval(auth_string)
   this_dbname = eval("connection.%(_dbname_)s" % access_information)
   this_collection = eval("this_dbname.%(collection_name)s" % {"collection_name":collection_name})
   this_collection.remove()
   this_collection.insert(exchanged_dot_to_string(inserting_values))
   connection.close()

def replace_dictvalues_into_mongodb(collection_name, inserting_values, replace_values):
   access_information = {"_dbname_":mongodb["dbname"], "_username_":mongodb["username"], "_password_":mongodb["password"]}
   connection = pymongo.MongoClient(mongodb["ip"],int(mongodb["port"]))
   auth_string = "connection.%(_dbname_)s.authenticate(\"%(_username_)s\",\"%(_password_)s\")" % access_information
   eval(auth_string)
   this_dbname = eval("connection.%(_dbname_)s" % access_information)
   this_collection = eval("this_dbname.%(collection_name)s" % {"collection_name":collection_name})
   this_collection.update(inserting_values, replace_values)
   connection.close()

def exact_findout(collection_name, inserting_values):
   access_information = {"_dbname_":mongodb["dbname"], "_username_":mongodb["username"], "_password_":mongodb["password"]}
   connection = pymongo.MongoClient(mongodb["ip"],int(mongodb["port"]))
   auth_string = "connection.%(_dbname_)s.authenticate(\"%(_username_)s\",\"%(_password_)s\")" % access_information
   eval(auth_string)
   this_dbname = eval("connection.%(_dbname_)s" % access_information)
   this_collection = eval("this_dbname.%(collection_name)s" % {"collection_name":collection_name})
   #findout_value = this_collection.find(exchanged_dot_to_string(inserting_values))
   findout_value = this_collection.find(inserting_values)
   connection.close()
   #return recovery_dot_from_string(dumps(findout_value))
   #return dumps(findout_value)
   return loads(dumps(findout_value))

def remove_collection(collection_name):
   access_information = {"_dbname_":mongodb["dbname"], "_username_":mongodb["username"], "_password_":mongodb["password"]}
   connection = pymongo.MongoClient(mongodb["ip"],int(mongodb["port"]))
   auth_string = "connection.%(_dbname_)s.authenticate(\"%(_username_)s\",\"%(_password_)s\")" % access_information
   eval(auth_string)
   this_dbname = eval("connection.%(_dbname_)s" % access_information)
   this_collection = eval("this_dbname.%(collection_name)s" % {"collection_name":collection_name})
   this_collection.remove()
   connection.close()

def remove_data_in_collection(collection_name, removing_values):
   access_information = {"_dbname_":mongodb["dbname"], "_username_":mongodb["username"], "_password_":mongodb["password"]}
   connection = pymongo.MongoClient(mongodb["ip"],int(mongodb["port"]))
   auth_string = "connection.%(_dbname_)s.authenticate(\"%(_username_)s\",\"%(_password_)s\")" % access_information
   eval(auth_string)
   this_dbname = eval("connection.%(_dbname_)s" % access_information)
   this_collection = eval("this_dbname.%(collection_name)s" % {"collection_name":collection_name})
   #removed_status = this_collection.remove(exchanged_dot_to_string(removing_values))
   removed_status = this_collection.remove(removing_values)
   connection.close()
   return removed_status

def insert_dictvalues_into_mongodb(collection_name, inserting_values):
   access_information = {"_dbname_":mongodb["dbname"], "_username_":mongodb["username"], "_password_":mongodb["password"]}
   connection = pymongo.MongoClient(mongodb["ip"],int(mongodb["port"]))
   auth_string = "connection.%(_dbname_)s.authenticate(\"%(_username_)s\",\"%(_password_)s\")" % access_information
   eval(auth_string)
   this_dbname = eval("connection.%(_dbname_)s" % access_information)
   this_collection = eval("this_dbname.%(collection_name)s" % {"collection_name":collection_name})
   #this_collection.insert(exchanged_dot_to_string(inserting_values))
   this_collection.insert(inserting_values)
   connection.close()

def insert_dictvalues_list_into_mongodb(collection_name, inserting_values_list):
   access_information = {"_dbname_":mongodb["dbname"], "_username_":mongodb["username"], "_password_":mongodb["password"]}
   connection = pymongo.MongoClient(mongodb["ip"],int(mongodb["port"]))
   auth_string = "connection.%(_dbname_)s.authenticate(\"%(_username_)s\",\"%(_password_)s\")" % access_information
   eval(auth_string)
   this_dbname = eval("connection.%(_dbname_)s" % access_information)
   this_collection = eval("this_dbname.%(collection_name)s" % {"collection_name":collection_name})
   for _inserting_values_ in inserting_values_list:
      #this_collection.insert(exchanged_dot_to_string(_inserting_values_))
      this_collection.insert(_inserting_values_)
   connection.close()   

   
def obtainjson_from_mongodb(collection_name):
   access_information = {"_dbname_":mongodb["dbname"], "_username_":mongodb["username"], "_password_":mongodb["password"]}
   connection = pymongo.MongoClient(mongodb["ip"],int(mongodb["port"]))
   auth_string = "connection.%(_dbname_)s.authenticate(\"%(_username_)s\",\"%(_password_)s\")" % access_information
   eval(auth_string)
   this_dbname = eval("connection.%(_dbname_)s" % access_information)
   this_collection = eval("this_dbname.%(collection_name)s" % {"collection_name":collection_name})
   _finded_string_ = dumps(this_collection.find())
   connection.close()
   #
   #_find_info_ = recovery_dot_from_string(_finded_string_) 
   #for _dict_ in _find_info_:
   #   del _dict_[u'_id']
   #return _find_info_
   _json_ = loads(_finded_string_);
   for _dict_ in _json_:
      del _dict_[u'_id']
   return _json_ 

def findout_primary_devices(_devices_infomations_):
   searched_list = []
   for _deviceinfo_ in _devices_infomations_:
      if (re.search(u'primary', _deviceinfo_[u'failover'], re.I)) or re.search('primary', str(_deviceinfo_[u'failover']), re.I):
        if _deviceinfo_[u'apiaccessip'] not in searched_list:
          searched_list.append(_deviceinfo_[u'apiaccessip'])
   return searched_list

def search_items_matched_info_by_apiaccessip(_devices_infomations_, _apiaccessip_):
   for _dict_item_ in _devices_infomations_:
      if re.search(str(_apiaccessip_),str(_dict_item_[u'apiaccessip']),re.I):
        return _dict_item_        

def info_iface_to_zonename(device_information_values):
   reversed_sorted_iface_to_zone = {}
   for _zonename_ in device_information_values[u'zonesinfo'].keys():
      for _ifacename_ in device_information_values[u'zonesinfo'][_zonename_].keys():
         reversed_sorted_iface_to_zone[_ifacename_] = _zonename_
   return reversed_sorted_iface_to_zone


def remove_info_in_db(dataDict_value, this_processor_queue, mongo_db_collection_name):
   remove_status = exact_findout(mongo_db_collection_name, dataDict_value)
   if len(remove_status):
     remove_data_in_collection(mongo_db_collection_name, dataDict_value) 
     return_object = {
           "items":[],
           "process_status":"done",
           "process_msg":"%(_removed_)s removed" % {"_removed_":str(dataDict_value[u'hostname'])}
     }
     this_processor_queue.put(return_object)
   else:
     return_object = {
           "items":[],
           "process_status":"error",
           "process_msg":"%(_removed_)s not matched to remove" % {"_removed_":str(dataDict_value[u'hostname'])}
     }
     this_processor_queue.put(return_object)

def _defaultClustering_in_db_(mongo_db_clusterGroup_collection_name, _dictValue_):
   remove_status = exact_findout(mongo_db_clusterGroup_collection_name, _dictValue_)
   if len(remove_status):
     for _removeDict_ in remove_status:
        _default_cluster_info_ = {u'hostname': _removeDict_[u'hostname'], u'hahostname':'none', u'clusterStatus':'none'}
        remove_data_in_collection(mongo_db_clusterGroup_collection_name, _removeDict_)
        insert_dictvalues_into_mongodb(mongo_db_clusterGroup_collection_name, _default_cluster_info_)


def _find_clusteringMember_(_deviceInfoDB_, _clusteringDB_, _dbKeyName_, _dbSearchValue_):
   #fromDB_infomations = exact_findout(_deviceInfoDB_,{"apiaccessip" : str(_ipAddress_)})
   fromDB_infomations = exact_findout(_deviceInfoDB_,{_dbKeyName_ : str(_dbSearchValue_)})
   _hostNamesList_ = []
   for _dictValue_ in fromDB_infomations:
      _stringValue_ = str(_dictValue_[u'hostname'])
      if _stringValue_ not in _hostNamesList_:
        _hostNamesList_.append(_stringValue_)
   #
   _hostNameEvery_ = copy.copy(_hostNamesList_)
   #
   for _hostName_ in _hostNamesList_:
      fromDB_infomations = exact_findout(_clusteringDB_,{"hostname":str(_hostName_), "clusterStatus" : "clustered"})
      if len(fromDB_infomations):
        for _dictFromDB_ in fromDB_infomations:
           _stringValue_ = str(_dictFromDB_[u'hahostname'])
           if _stringValue_ not in _hostNameEvery_:
             _hostNameEvery_.append(_stringValue_)
   #
   return _hostNameEvery_ 







