#! /usr/bin/env python


from setting import GW_HOST,GW_PORT,CHART_DATA_NUMBER,ROLLBAK_INTERVAL

from flask import render_template
import os,json,re,time,copy,sys

def active_device_ip(ipaddress):

   ip_address = str(ipaddress)

   bash_command = "curl http://%(GW_HOST)s:%(GW_PORT)s/f5/devicelist/" % {"GW_HOST":GW_HOST,"GW_PORT":GW_PORT}
   bash_return = os.popen(bash_command).read().strip()
   json_loads_value = json.loads(bash_return)

   haclustername = False
   for _dict_ in json_loads_value:
      if re.search(ip_address,str(_dict_[u'ip']),re.I):
        if re.match("active",str(_dict_[u'failover']),re.I):
          active_device = str(ip_address)
          return active_device
        else:
          haclustername = str(_dict_[u'haclustername'])
   
   if haclustername:     
      for _dict_ in json_loads_value:
         if re.search(haclustername,str(_dict_[u'clustername']),re.I):
           if re.match("active",str(_dict_[u'failover']),re.I):
             active_device = str(_dict_[u'ip'])
             return active_device


def toprank_extract(matched_callable_device_active_name,unicode_key_list,json_loads_value,toprank_return):
   # init return box
   for _ukey_ in unicode_key_list:
      toprank_return[_ukey_] = []
   # extract the top rank target
   json_loads_value_keyname = json_loads_value.keys()
   for _keyname_ in json_loads_value_keyname:
      if re.search(matched_callable_device_active_name,str(_keyname_),re.I):
        for _ukey_ in unicode_key_list:
           rank_dict = json_loads_value[_keyname_][_ukey_]
           rank_dict_key = rank_dict.keys()
           for _rkey_ in rank_dict_key:
              _vserverlist_ = rank_dict[_rkey_][u'virtualservers']
              for _vname_ in _vserverlist_:
                 _vname_string_ = str(_vname_)
                 if _vname_string_ not in toprank_return[_ukey_]:
                   toprank_return[_ukey_].append(_vname_string_)
   # return 
   return toprank_return 


def obtain_draw_data(_this_Dict_,matched_callable_device_active_name,backtotime_interval):
   _this_Dict_keyname_ = _this_Dict_.keys()
   return_list = {}
   for _keyname_ in _this_Dict_keyname_:
  
      return_list[_keyname_] = []

      # matched virtual server infor
      this_virtualserver_list = _this_Dict_[_keyname_]

      # memory database
      memory_this_db = {}
      for _vname_ in this_virtualserver_list:
         _vname_string_ = str(_vname_)
         _vname_stats_filename_ = "%(_vname_string_)s@%(matched_callable_device_active_name)s" % {"_vname_string_":_vname_string_,"matched_callable_device_active_name":matched_callable_device_active_name}
         bash_command = "curl http://%(GW_HOST)s:%(GW_PORT)s/f5/stats/virtual/%(virtualhostname)s/" % {"GW_HOST":GW_HOST,"GW_PORT":GW_PORT,"virtualhostname":_vname_string_}
         bash_return = os.popen(bash_command).read().strip()
         json_loads_value = json.loads(bash_return)
         for _dictData_ in json_loads_value:
            _dictData_keyname_ = _dictData_.keys()
            for _key_ in _dictData_keyname_:
               if re.search(_vname_stats_filename_,str(_key_),re.I):
                 memory_this_db[_vname_] = _dictData_[_key_]

      # find out basic time line
      _basic_standard_ = str(this_virtualserver_list[-1])
      unicode_timevalue_list = memory_this_db[_basic_standard_].keys()
      unicode_timevalue_list.sort()

      # start end time value calculation
      last_time = unicode_timevalue_list[-1]
      predicted_past_time = float(last_time)-float(backtotime_interval)
      findabs_box = {}
      for _univalue_ in unicode_timevalue_list:
         abs_interval_value = abs(float(_univalue_)-float(predicted_past_time))
         findabs_box[abs_interval_value] = _univalue_
      findabs_box_keys = findabs_box.keys()
      findabs_box_keys.sort()
      matched_final_time = findabs_box[findabs_box_keys[0]]

      matched_index = unicode_timevalue_list.index(matched_final_time)
      included_matched_index = matched_index + int(1)

      valid_timevalue = []
      if matched_index <= CHART_DATA_NUMBER:
        valid_timevalue = unicode_timevalue_list[:included_matched_index]
      else:
        start_index = int(matched_index - CHART_DATA_NUMBER)
        valid_timevalue = unicode_timevalue_list[start_index:included_matched_index]

      # find out the data match
      each_list_item_sum = []
      title_list = ["time"]
      for _utime_ in valid_timevalue:
         each_list_item = []
         # time string added
         ctime_string = time.ctime(float(_utime_))
         parsed_date = ctime_string.strip().split()
         express_time = str("/".join([parsed_date[1],parsed_date[2],str(":".join(parsed_date[3].strip().split(':')[:2]))]))
         each_list_item.append(express_time)
         # value according to string 
         for _vname_ in this_virtualserver_list:
            _vname_string_ = str(_vname_)
            # title insert
            if _vname_string_ not in title_list:
              title_list.append(_vname_string_)
            # data insert
            from_memory_to_match = memory_this_db[_vname_]
            timeinlist = from_memory_to_match.keys()
            timecompare_box = {}
            for timein in timeinlist:
               abs_interval_value = abs(float(timein)-float(_utime_))
               timecompare_box[abs_interval_value] = timein
            timecompare_box_keyname = timecompare_box.keys()
            timecompare_box_keyname.sort()
            close_time_value = timecompare_box[timecompare_box_keyname[0]]
            each_list_item.append(from_memory_to_match[close_time_value][_keyname_])
         # line change according to time
         each_list_item_sum.append(each_list_item)
      # insert title at the first
      each_list_item_sum.insert(0,title_list)
      return_list[_keyname_] = each_list_item_sum
   return return_list
      

def stats_top_chart(target,before_time):

    _devicename_ = str(target)
    backtotime_interval = int(int(ROLLBAK_INTERVAL)*int(before_time))

    bash_command = "curl http://%(GW_HOST)s:%(GW_PORT)s/f5/devicelist/" % {"GW_HOST":GW_HOST,"GW_PORT":GW_PORT}
    bash_return = os.popen(bash_command).read().strip()
    json_loads_value = json.loads(bash_return)

    matched_callable_device_ip = None
    for _device_Dict_ in json_loads_value:
       if re.search(_devicename_,str(_device_Dict_[u'clustername']),re.I) or re.search(_devicename_,str(_device_Dict_[u'devicehostname']),re.I):
         matched_callable_device_ip = str(_device_Dict_[u'ip']) 
    if not matched_callable_device_ip:
      return "host name is not proper!"

    matched_callable_device_active_name = None
    matched_callable_device_active_ip = active_device_ip(matched_callable_device_ip)
    for _device_Dict_ in json_loads_value:
       if re.search(matched_callable_device_active_ip,str(_device_Dict_[u'ip']),re.I):
         matched_callable_device_active_name = str(_device_Dict_[u'devicehostname'])
    if not matched_callable_device_active_name:
      return "active device name is not proper!"

    ## toprank : bps
    bash_command = "curl http://%(GW_HOST)s:%(GW_PORT)s/f5/stats/virtual/top/bps/" % {"GW_HOST":GW_HOST,"GW_PORT":GW_PORT}
    bash_return = os.popen(bash_command).read().strip()
    json_loads_value = json.loads(bash_return)   
    unicode_key_list = [u'bpsOut',u'bpsIn']
    bps_toprank_virtualserver = toprank_extract(matched_callable_device_active_name,unicode_key_list,json_loads_value,{})


    ## toprank : pps
    bash_command = "curl http://%(GW_HOST)s:%(GW_PORT)s/f5/stats/virtual/top/pps/" % {"GW_HOST":GW_HOST,"GW_PORT":GW_PORT}
    bash_return = os.popen(bash_command).read().strip()
    json_loads_value = json.loads(bash_return)
    unicode_key_list = [u'ppsOut',u'ppsIn']
    pps_toprank_virtualserver = toprank_extract(matched_callable_device_active_name,unicode_key_list,json_loads_value,{})

    ## toprank : cps
    bash_command = "curl http://%(GW_HOST)s:%(GW_PORT)s/f5/stats/virtual/top/cps/" % {"GW_HOST":GW_HOST,"GW_PORT":GW_PORT}
    bash_return = os.popen(bash_command).read().strip()
    json_loads_value = json.loads(bash_return)
    unicode_key_list = [u'cps']
    cps_toprank_virtualserver = toprank_extract(matched_callable_device_active_name,unicode_key_list,json_loads_value,{})
 
    ## toprank : session
    bash_command = "curl http://%(GW_HOST)s:%(GW_PORT)s/f5/stats/virtual/top/session/" % {"GW_HOST":GW_HOST,"GW_PORT":GW_PORT}
    bash_return = os.popen(bash_command).read().strip()
    json_loads_value = json.loads(bash_return)
    unicode_key_list = [u'session']
    session_toprank_virtualserver = toprank_extract(matched_callable_device_active_name,unicode_key_list,json_loads_value,{}) 

    bpstop = obtain_draw_data(bps_toprank_virtualserver,matched_callable_device_active_name,backtotime_interval)
    bpsout_top = bpstop[u'bpsOut']
    bpsin_top = bpstop[u'bpsIn']

    ppstop = obtain_draw_data(pps_toprank_virtualserver,matched_callable_device_active_name,backtotime_interval)
    ppsout_top = ppstop[u'ppsOut']
    ppsin_top = ppstop[u'ppsIn']

    cpstop = obtain_draw_data(cps_toprank_virtualserver,matched_callable_device_active_name,backtotime_interval)
    cps_top = cpstop[u'cps']

    sessiontop = obtain_draw_data(session_toprank_virtualserver,matched_callable_device_active_name,backtotime_interval)
    session_top = sessiontop[u'session']

    #
    return render_template('f5/stats_top_chart.html', matched_callable_device_active_name=matched_callable_device_active_name,bpsout_top=bpsout_top, bpsin_top=bpsin_top, ppsout_top=ppsout_top, ppsin_top=ppsin_top, cps_top=cps_top, session_top=session_top)

