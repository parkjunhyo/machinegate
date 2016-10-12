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

def virtual_profile_clientside():
   
    bash_command = "curl http://%(GW_HOST)s:%(GW_PORT)s/f5/virtualserverlist/profile/clientside/" % {"GW_HOST":GW_HOST,"GW_PORT":GW_PORT}
    bash_return = os.popen(bash_command).read().strip()
    json_loads_value = json.loads(bash_return)


    allData_list = []
    for _dictData_ in json_loads_value:

       _dictData_keynames_ = _dictData_.keys()
       if len(_dictData_keynames_) != 0:

         for _deviceipaddress_ in _dictData_keynames_:
            activedevicename = active_device_ip(_deviceipaddress_)
            certkeyname_in_host = _dictData_[_deviceipaddress_].keys()
            if len(certkeyname_in_host) != 0:

              for _certkeyname_ in certkeyname_in_host:

                 certgroupnames = _dictData_[_deviceipaddress_][_certkeyname_][u'certKeyChain'].keys()
                 used_vnames = str("\n".join(_dictData_[_deviceipaddress_][_certkeyname_][u'virtualservers']))

                 if len(certgroupnames) != 0:

                   for _certgroupname_ in certgroupnames:

                      itemData = _dictData_[_deviceipaddress_][_certkeyname_][u'certKeyChain'][_certgroupname_]
                      itemDatakeyname = itemData.keys()

                      basic_listvalues = [str(activedevicename),str(_certkeyname_),str(used_vnames),str(_certgroupname_)]

                      if unicode("cert") in itemDatakeyname:
                        matched_name = itemData[unicode("cert")][u'name']
                        basic_listvalues.append(str(matched_name))
                        matched_exptime = itemData[unicode("cert")][u'expirationString']
                        basic_listvalues.append(str(matched_exptime))
                        exptime = float(itemData[unicode("cert")][u'expirationDate'])
                        calc_exptime = calculate_expire_time(exptime)
                        basic_listvalues.append(calc_exptime)
                         
                      else:
                        basic_listvalues.append(str("-"))
                        basic_listvalues.append(str("-"))
                        basic_listvalues.append(str("-"))

                      if unicode("key") in itemDatakeyname:
                        matched_name = itemData[unicode("key")][u'name']
                        basic_listvalues.append(str(matched_name))
                      else:
                        basic_listvalues.append(str("-"))

                      if unicode("chain") in itemDatakeyname:
                        matched_name = itemData[unicode("chain")][u'name']
                        basic_listvalues.append(str(matched_name))
                        matched_exptime = itemData[unicode("chain")][u'expirationString']
                        basic_listvalues.append(str(matched_exptime))
                        exptime = float(itemData[unicode("chain")][u'expirationDate'])
                        calc_exptime = calculate_expire_time(exptime)
                        basic_listvalues.append(calc_exptime)

                      else:
                        basic_listvalues.append(str("-"))
                        basic_listvalues.append(str("-"))
                        basic_listvalues.append(str("-"))

                      allData_list.append(basic_listvalues)


    return render_template('f5/virtual_profile_clientside.html', allData_list=allData_list)
    #return render_template('f5/stats_chart.html', GW_HOST=GW_HOST,virtualhostname=virtualhostname,activedevicename=activedevicename,bps_chart=bps_chart,pps_chart=pps_chart,cps_chart=cps_chart,session_chart=session_chart)

