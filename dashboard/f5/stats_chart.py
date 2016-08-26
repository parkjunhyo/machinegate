#! /usr/bin/env python


from setting import GW_HOST,GW_PORT

from flask import render_template
import os,json,re

def stats_chart(target):

    target_string = str(target)

    splited_target_string = target_string.strip().split("@")
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
    print whatismyip
    

    bash_command = "curl http://%(GW_HOST)s:%(GW_PORT)s/f5/stats/virtual/" % {"GW_HOST":GW_HOST,"GW_PORT":GW_PORT}
    bash_return = os.popen(bash_command).read().strip()
    json_loads_value = json.loads(bash_return)
 
    match_status = False
    virtualserver_dict = {}
    devicehost_ipaddress_list = json_loads_value.keys()
    for ipaddress in devicehost_ipaddress_list:
       ipaddress_string = str(ipaddress)       
       virtualserverlist = json_loads_value[ipaddress].keys()
       virtualserver_list = []
       for virtualserver in virtualserverlist:
           virtualserver_string = str(virtualserver)
           if virtualserver_string not in virtualserver_list:
             virtualserver_list.append(virtualserver_string)
       if ipaddress_string not in virtualserver_dict.keys():
         virtualserver_dict[ipaddress_string] = virtualserver_list

    match_status = False
    for ipaddress in virtualserver_dict.keys():
       for virtualserver in virtualserver_dict[ipaddress]:
          if re.match(target_string,virtualserver,re.I):
            match_status = True
            break
    if not match_status:
      return "virtualserver name is required!"
            
    #return json.dumps(virtualserver_dict)
    #print stream
    #print JSONParser().parse(stream)
    #sample_dict = {"v_198.50_homeoffice":["192.168.0.1","192.168.0.2"],"v_206.50_myhome":["192.3.1.1","192.5.1.2"]}
    #return render_template('f5/stats_chart.html', name=target_string, sample_dict=sample_dict)

    return render_template('f5/stats_chart.html', name=target_string)

    #return 'Hello World!'

#def route_hello(name=None):
#    return render_template('f5/hello.html', name=name)
