#! /usr/bin/env python


from setting import GW_HOST,GW_PORT,RUN_PORT,RUN_HOST

from flask import render_template
import os,json,re

def stats_virtual_list():


    bash_command = "curl http://%(GW_HOST)s:%(GW_PORT)s/f5/stats/virtual/" % {"GW_HOST":GW_HOST,"GW_PORT":GW_PORT}
    bash_return = os.popen(bash_command).read().strip()
    json_loads_value = json.loads(bash_return)

    devicehostiplist = json_loads_value.keys()
    devicehost_virtuallist_dict = {}    
    for ipaddress in devicehostiplist:
       ipaddress_string = str(ipaddress)
       virtualnamelist = []
       for virtualname in json_loads_value[ipaddress].keys():
          virtualname_string = str(virtualname)
          if virtualname_string not in virtualnamelist:
            virtualnamelist.append(virtualname_string)
       devicehost_virtuallist_dict[ipaddress_string] = virtualnamelist

    bash_command = "curl http://%(GW_HOST)s:%(GW_PORT)s/f5/devicelist/" % {"GW_HOST":GW_HOST,"GW_PORT":GW_PORT}
    bash_return = os.popen(bash_command).read().strip()
    json_loads_value = json.loads(bash_return)

    deviceip_devicehostname_dict = {}
    for dictData in json_loads_value:
       ipaddress_string = str(dictData[u'ip'])
       hostnames_list = []
       for name in [str(dictData[u'devicehostname']),str(dictData[u'clustername'])]:
          if name not in hostnames_list:
            hostnames_list.append(name)
       if ipaddress_string not in deviceip_devicehostname_dict.keys():
         deviceip_devicehostname_dict[ipaddress_string] = hostnames_list 
       
    return render_template('f5/stats_virtual_list.html', RUN_PORT=RUN_PORT,RUN_HOST=RUN_HOST,devicehost_virtuallist_dict=devicehost_virtuallist_dict, deviceip_devicehostname_dict=deviceip_devicehostname_dict)
