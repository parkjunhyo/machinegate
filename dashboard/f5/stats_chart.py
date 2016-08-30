#! /usr/bin/env python


from setting import GW_HOST,GW_PORT,CHART_DATA_NUMBER,ROLLBAK_INTERVAL

from flask import render_template
import os,json,re,time,copy

def stats_chart(target,before_time):

    backtotime_interval = int(int(ROLLBAK_INTERVAL)*int(before_time)) 
    target_string = str(target)

    if re.search('@',target_string,re.I):
      splited_target_string = target_string.strip().split("@")
    elif re.search('%',target_string,re.I):
      splited_target_string = target_string.strip().split("%")
    else:
      return "virtualserver@device name is required!"
      
    if len(splited_target_string) != 2:
      return "virtualserver@device name is required!"

    [ virtualhostname, activedevicename ] = splited_target_string 

    bash_command = "curl http://%(GW_HOST)s:%(GW_PORT)s/f5/devicelist/" % {"GW_HOST":GW_HOST,"GW_PORT":GW_PORT}
    bash_return = os.popen(bash_command).read().strip()
    json_loads_value = json.loads(bash_return)
    whatismyip = None
    for dictData in json_loads_value:
       if re.search(activedevicename,str(dictData[u'clustername']),re.I) or re.search(activedevicename,str(dictData[u'devicehostname']),re.I):
         whatismyip = str(dictData[u'ip']) 


    bash_command = "curl http://%(GW_HOST)s:%(GW_PORT)s/f5/stats/virtual/" % {"GW_HOST":GW_HOST,"GW_PORT":GW_PORT}
    bash_return = os.popen(bash_command).read().strip()
    json_loads_value = json.loads(bash_return)
 
    match_status = False
    virtualserver_dict = {}
    devicehost_ipaddress_list = json_loads_value.keys()
    for ipaddress in devicehost_ipaddress_list:
       ipaddress_string = str(ipaddress)       
       if re.match(whatismyip,ipaddress_string,re.I):
         virtualserverlist = json_loads_value[ipaddress].keys()
         virtualserver_list = []
         for virtualserver in virtualserverlist:
            virtualserver_string = str(virtualserver)
            if re.match(virtualhostname,virtualserver_string,re.I):
              match_status = True

    if not match_status:
      return "proper virtualserver name is required!"

    bash_command = "curl http://%(GW_HOST)s:%(GW_PORT)s/f5/stats/virtual/%(virtualhostname)s/" % {"GW_HOST":GW_HOST,"GW_PORT":GW_PORT,"virtualhostname":virtualhostname}
    bash_return = os.popen(bash_command).read().strip()
    json_loads_value = json.loads(bash_return)


    float_timevalue_list = []
    stats_dataDict = json_loads_value[-1].values()[-1]
    unicode_timevalue_list = stats_dataDict.keys()
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

    #valid_timevalue = []
    #if len(float_timevalue_list) <= CHART_DATA_NUMBER:
    #  valid_timevalue = unicode_timevalue_list 
    #else:
    #  valid_timevalue = unicode_timevalue_list[(len(unicode_timevalue_list)-CHART_DATA_NUMBER):]

    bpspps_chart_init_data_list = [["time","in","out","total"]]
    cpsseion_chart_init_data_list = [["time","value"]]

    bps_chart = copy.copy(bpspps_chart_init_data_list)
    pps_chart = copy.copy(bpspps_chart_init_data_list)
    cps_chart = copy.copy(cpsseion_chart_init_data_list)
    session_chart = copy.copy(cpsseion_chart_init_data_list)

    for _valid_time_ in valid_timevalue:

       # time variable
       time_string = time.ctime(stats_dataDict[_valid_time_][u'updated_time'])
       selected_time = [ time_string.strip().split()[1], time_string.strip().split()[2], str(":".join(time_string.strip().split()[3].split(":")[:2]))]
       parsed_time_string = str("/".join(selected_time))

       # bps
       bpsin = stats_dataDict[_valid_time_][u'bpsIn']
       bpsout = stats_dataDict[_valid_time_][u'bpsOut']
       bps_chart.append([parsed_time_string,bpsin,bpsout,bpsin+bpsout])

       # pps
       ppsin = stats_dataDict[_valid_time_][u'ppsIn']
       ppsout = stats_dataDict[_valid_time_][u'ppsOut']
       pps_chart.append([parsed_time_string,ppsin,ppsout,ppsin+ppsout])

       # cps
       cps = stats_dataDict[_valid_time_][u'cps']
       cps_chart.append([parsed_time_string,cps])

       # session
       session = stats_dataDict[_valid_time_][u'session']
       session_chart.append([parsed_time_string,session])

    return render_template('f5/stats_chart.html', virtualhostname=virtualhostname,activedevicename=activedevicename,bps_chart=bps_chart,pps_chart=pps_chart,cps_chart=cps_chart,session_chart=session_chart)

