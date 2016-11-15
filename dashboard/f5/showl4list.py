#! /usr/bin/env python


from setting import GW_HOST,GW_PORT,CHART_DATA_NUMBER

from flask import render_template
import os,json,re,time,copy


def active_device_ip(ipaddress):

   ip_address = str(ipaddress)

   bash_command = "curl http://%(GW_HOST)s:%(GW_PORT)s/f5/devicelist/" % {"GW_HOST":GW_HOST,"GW_PORT":GW_PORT}
   bash_return = os.popen(bash_command).read().strip()
   json_loads_value = json.loads(bash_return)

   haclustername = False
   for _dict_ in json_loads_value:
      if re.search(ip_address,str(_dict_[u'ip']),re.I):
        if re.match("active",str(_dict_[u'failover']),re.I):
          #active_device = str(ip_address)
          active_device = str(_dict_[u'devicehostname'])
          return active_device
        else:
          haclustername = str(_dict_[u'haclustername'])
   
   if haclustername:     
      for _dict_ in json_loads_value:
         if re.search(haclustername,str(_dict_[u'clustername']),re.I):
           if re.match("active",str(_dict_[u'failover']),re.I):
             #active_device = str(_dict_[u'ip'])
             active_device = str(_dict_[u'devicehostname'])
             return active_device

def calculate_expire_time(exptime):
   current_time = float(time.time())
   day_gap = (exptime - current_time)/86400
   str_int_abs_day_gap = str(int(abs(day_gap)))
   if day_gap >= 0:
     calc_exptime = str("".join(['(-)',str_int_abs_day_gap]))
   else:
     calc_exptime = str("".join(['(+)',str_int_abs_day_gap]))
   return calc_exptime

def showl4list():
   
    bash_command = "curl http://%(GW_HOST)s:%(GW_PORT)s/f5/virtualserverlist/" % {"GW_HOST":GW_HOST,"GW_PORT":GW_PORT}
    bash_return = os.popen(bash_command).read().strip()
    json_loads_value = json.loads(bash_return)
    database_virtualserver = {}
    for dictvalue in json_loads_value:
       dictvalue_keyname = dictvalue.keys()
       for _keyname_ in dictvalue_keyname:
          if _keyname_ not in database_virtualserver.keys():
            vip_persist_string = "(%(vip_ip)s/%(persist_value)s)" % {"vip_ip":str(str(dictvalue[_keyname_][u"destination"]).strip().split("/")[-1]),"persist_value":str(dictvalue[_keyname_][u"persist"])}
            database_virtualserver[str(str(_keyname_).strip().split("/")[-1])] = vip_persist_string


    bash_command = "curl http://%(GW_HOST)s:%(GW_PORT)s/f5/devicelist/" % {"GW_HOST":GW_HOST,"GW_PORT":GW_PORT}
    bash_return = os.popen(bash_command).read().strip()
    json_loads_value = json.loads(bash_return)

    database_device = {}
    for dictvalue in json_loads_value:
       if str(dictvalue[u"mgmtip"]) not in database_device.keys():
         database_device[str(dictvalue[u"mgmtip"])] = str(dictvalue[u"devicehostname"])
       if str(dictvalue[u"ip"]) not in database_device.keys():
         database_device[str(dictvalue[u"ip"])] = str(dictvalue[u"devicehostname"])


    bash_command = "curl http://%(GW_HOST)s:%(GW_PORT)s/f5/poolmemberlist/" % {"GW_HOST":GW_HOST,"GW_PORT":GW_PORT}
    bash_return = os.popen(bash_command).read().strip()
    json_loads_value = json.loads(bash_return)

    device_iplist = json_loads_value.keys()
    l4bind_info = []
    for _deviceip_ in device_iplist:
       _deviceip_string_ = str(_deviceip_)
       _poolname_in_device_ = json_loads_value[_deviceip_].keys()
       for _poolname_ in _poolname_in_device_:
          list_box = []
          # poolname
          list_box.append(str(_poolname_))
          # device
          if _deviceip_string_ not in database_device.keys():
            list_box.append("no device")
          else:
            list_box.append(database_device[_deviceip_string_])
          # virtual ip
          if len(json_loads_value[_deviceip_][_poolname_][u"virtualserver_names"]) == 0:
            list_box.append("no assigned") 
          else:
             valid_virtualinfo = []
             for _virtualinfo_ in json_loads_value[_deviceip_][_poolname_][u"virtualserver_names"]:
                if str(_virtualinfo_) in database_virtualserver.keys():
                  valid_virtualinfo.append(str(_virtualinfo_)+database_virtualserver[str(_virtualinfo_)])
                else:
                  valid_virtualinfo.append(str(_virtualinfo_)+str("(no properity)"))
             list_box.append(str(";".join(valid_virtualinfo)))
          # pool member ip "poolmembers_status"
          if len(json_loads_value[_deviceip_][_poolname_][u"poolmembers_status"].keys()) == 0:
            list_box.append("no poolmember")
          else:
            memberip_list = []
            for poolipaddr in json_loads_value[_deviceip_][_poolname_][u"poolmembers_status"].keys():
               memberip_string = str(str(poolipaddr).strip().split("/")[-1])
               if memberip_string not in memberip_list:
                 memberip_list.append(memberip_string)
            list_box.append(str(";".join(memberip_list)))
          # mode
          if unicode("loadBalancingMode") not in json_loads_value[_deviceip_][_poolname_].keys():
            list_box.append("no defined")
          else:
            list_box.append(str(json_loads_value[_deviceip_][_poolname_][u"loadBalancingMode"]))
          # monitor 
          if unicode("monitors") not in json_loads_value[_deviceip_][_poolname_].keys():
            list_box.append("no monitoring")
          else:
            valid_virtualinfo = []
            for _virtualinfo_ in json_loads_value[_deviceip_][_poolname_][u"monitors"]:
               valid_virtualinfo.append(str(str(_virtualinfo_).strip().split("/")[-1]))
            list_box.append(str(";".join(valid_virtualinfo)))
          # insert all  
          l4bind_info.append(list_box)

    return render_template('f5/showl4list.html', allData_list=l4bind_info)
    #return render_template('f5/stats_chart.html', GW_HOST=GW_HOST,virtualhostname=virtualhostname,activedevicename=activedevicename,bps_chart=bps_chart,pps_chart=pps_chart,cps_chart=cps_chart,session_chart=session_chart)

