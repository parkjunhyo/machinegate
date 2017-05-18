from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.renderers import JSONRenderer
from rest_framework.parsers import JSONParser

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils.six import BytesIO

#from juniperapi.setting import USER_DATABASES_DIR
from juniperapi.setting import USER_NAME
from juniperapi.setting import USER_PASSWORD
from juniperapi.setting import ENCAP_PASSWORD
from juniperapi.setting import RUNSERVER_PORT
from juniperapi.setting import PARAMIKO_DEFAULT_TIMEWAIT
#from juniperapi.setting import USER_VAR_CHCHES
from juniperapi.setting import PYTHON_MULTI_PROCESS
from juniperapi.setting import PYTHON_MULTI_THREAD
from juniperapi.setting import system_property

import os,re,copy,json,time,threading,sys,random
import paramiko
import radix, math
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


################################################################################################################################


def removeIncluded_netAddress(netList):
   count = len(netList)
   while(count):
      popElement = netList.pop()
      ipNet_popElement = IPNetwork(popElement)
      inCludeStatus = True
      for element in netList:
         ipNet_element = IPNetwork(element)
         if ipNet_popElement in ipNet_element:
           inCludeStatus = False
           break
      if inCludeStatus:
        netList.insert(0, popElement)
      count = count - 1
   #
   return netList
  
def findMaxSubnetSize(netList):
   subnetNumber = []
   for element in netList:
      element_subnetInt = int(element.strip().split('/')[-1])
      if element_subnetInt not in subnetNumber:
        subnetNumber.append(element_subnetInt)
   subnetNumber.sort()
   maxSubnetNumber = subnetNumber[-1] 
   return maxSubnetNumber

###########################################################
# confirm addresses in the list are included in big size address 
###########################################################
def checkSubnetStatus(netList, copiedSrcIpString):
   maxSubnetNumber = findMaxSubnetSize(netList)
   # covered address count sum
   countSum = 0
   for netElement in netList:
      netElement_subnetSize = int(netElement.strip().split('/')[-1])
      countSum = countSum + int(math.pow(2, int(maxSubnetNumber - netElement_subnetSize)))   
   #
   copiedSrcIpString_subnetSize = int(copiedSrcIpString.strip().split('/')[-1])
   copiedSrcIpString_itemCount = int(math.pow(2, int(maxSubnetNumber - copiedSrcIpString_subnetSize)))
   #
   return int(copiedSrcIpString_itemCount - countSum)
   

###########################################################
# this is routing engin 
###########################################################
def findOutNextHop_RoutingEngin(rtree, copiedSrcIpString):
   matchedRoutingList = []
   rnodes = rtree.search_covered(copiedSrcIpString)
   if len(rnodes):
     #
     prefixValuesFromRnodes = []
     for _rnode_ in rnodes:
        prefixValuesFromRnodes.append(str(_rnode_.prefix))
     #
     netList = removeIncluded_netAddress(prefixValuesFromRnodes)
     #
     for _rNode_ in rnodes:
        _description_ = str(_rNode_.data["nextHop"]).strip()
        if _description_ not in matchedRoutingList:
          matchedRoutingList.append(_description_)
     #
     if checkSubnetStatus(netList, copiedSrcIpString) > 0:
       rnode = rtree.search_best(copiedSrcIpString)
       if rnode:
         _description_ = str(rnode.data["nextHop"]).strip()
         if _description_ not in matchedRoutingList:
           matchedRoutingList.append(_description_)      
   else:
     rnode = rtree.search_best(copiedSrcIpString)
     if rnode:
       _description_ = str(rnode.data["nextHop"]).strip()
       if _description_ not in matchedRoutingList:
         matchedRoutingList.append(_description_)
   return matchedRoutingList

   

def findOut_fwAndZone(_element_, inputObject, this_processor_queue):
   # find valid zone
   validZoneList = []
   _fromDB_values_ = exact_findout('juniperSrx_devicesInfomation', {"hostname":_element_, "zoneValidation" : "enable"})
   for _dictValue_ in _fromDB_values_:
      _stringInsert_ = {
              'from_zone':str(_dictValue_[u'from_zone']).strip(),
              'to_zone':str(_dictValue_[u'to_zone']).strip()
      }
      _uniqueString_ = "%(from_zone)s %(to_zone)s" % _stringInsert_
      if _uniqueString_ not in validZoneList:
        validZoneList.append(_uniqueString_)

   # routing engin create
   rtree = radix.Radix()
   #
   _fromDB_values_ = exact_findout('juniperSrx_routingTable', {"hostname":_element_})
   for _dictValue_ in _fromDB_values_:
      #
      _hostNameString_ = str(_dictValue_[u'hostname']).strip()
      _zoneNameString_ = str(_dictValue_[u'zonename']).strip()
      _routingAddressString_ = str(_dictValue_[u'routing_address']).strip()
      #
      descriptionString = "%(_hostNameString_)s %(_zoneNameString_)s" % {"_hostNameString_":_hostNameString_, "_zoneNameString_":_zoneNameString_}
      #
      rnode = rtree.add(_routingAddressString_)
      rnode.data["nextHop"] = descriptionString

   # address definition
   srcIpString = str(inputObject[u'srcIp']).strip()
   dstIpString = str(inputObject[u'dstIp']).strip()
   #
   copiedSrcIpString = copy.copy(srcIpString)
   copiedDstIpString = copy.copy(dstIpString)
   # 
   if re.search("^all$", copiedSrcIpString, re.I):
     copiedSrcIpString = "0.0.0.0/0"
   if re.search("^all$", copiedDstIpString, re.I):
     copiedDstIpString = "0.0.0.0/0"

   # routing engin search
   memberSrcList = findOutNextHop_RoutingEngin(rtree, copiedSrcIpString)
   memberDstList = findOutNextHop_RoutingEngin(rtree, copiedDstIpString)

   #
   for _sourceElement_ in memberSrcList:
      _sourceZoneName_ = _sourceElement_.strip().split()[-1]
      for _destinationElement_ in memberDstList:
         _destinationZoneName_ = _destinationElement_.strip().split()[-1]
         #
         if not (re.search(_sourceZoneName_, _destinationZoneName_, re.I) and re.search(_destinationZoneName_, _sourceZoneName_, re.I)):
           _stringInsert_ = {
                   'hostname':_element_,
                   'from_zone':_sourceZoneName_,
                    'to_zone':_destinationZoneName_
           }
           _uniqueString_ = "%(from_zone)s %(to_zone)s" % _stringInsert_
           if _uniqueString_ in validZoneList:
             this_processor_queue.put(_stringInsert_)
   #
   time.sleep(1)
 
##########################################
# match process common
##########################################
def applicationPortStringConverter(thisAppProtocolString, thisSrcPortString):
   insertDictValue = {'thisAppProtocolString':thisAppProtocolString, 'thisSrcPortString':thisSrcPortString}
   if re.search('^tcp$', thisAppProtocolString, re.I) or re.search('^udp$', thisAppProtocolString, re.I):
     if re.search('^all$', thisSrcPortString, re.I):
       thisSrcPortString = 'all'
     elif re.search('^0-65535$', thisSrcPortString, re.I):
       thisSrcPortString = "%(thisAppProtocolString)s/0-65535" % insertDictValue
     else:
       thisSrcPortString = "%(thisAppProtocolString)s/%(thisSrcPortString)s-%(thisSrcPortString)s" % insertDictValue
   elif re.search('^0$', thisAppProtocolString, re.I):
     if re.search('^all$', thisSrcPortString, re.I):
       thisSrcPortString = 'all'
     else:
       thisSrcPortString = "%(thisAppProtocolString)s/0-65535" % insertDictValue
   else:
     thisSrcPortString = thisAppProtocolString 
   return thisSrcPortString

def interSectionLoop(perfectMatchList):
   inerSectionList = perfectMatchList.pop()
   while (len(perfectMatchList)):
        compareTarget = perfectMatchList.pop()
        inerSectionList = list(set(inerSectionList).intersection(compareTarget))
   return inerSectionList

def returnStringOutput(inputObject):
   #
   thisSrcIp = inputObject[u'srcIp']
   thisSrcIpString = str(thisSrcIp).strip()
   thisDstIp = inputObject[u'dstIp']
   thisDstIpString = str(thisDstIp).strip()
   #
   thisAppProtocol = inputObject[u'appProtocol']
   thisAppProtocolString = str(thisAppProtocol).strip().lower()
   #
   thisSrcPort = inputObject[u'srcPort']
   thisSrcPortString = str(thisSrcPort).strip()
   thisSrcPortString = applicationPortStringConverter(thisAppProtocolString, thisSrcPortString)
   #   
   thisDstPort = inputObject[u'dstPort']
   thisDstPortString = str(thisDstPort).strip()
   thisDstPortString = applicationPortStringConverter(thisAppProtocolString, thisDstPortString)
   #
   thisAction = inputObject[u'action']
   thisActionString = str(thisAction).strip()
   #
   return thisSrcIpString, thisDstIpString, thisAppProtocolString, thisSrcPortString, thisDstPortString, thisActionString

##############################################
# perfect match processor
##############################################
def perfectMatch_valueSearch(_element_, _typeValue_, thisSrcIp):
   valuesForQuery = copy.copy(_element_)
   valuesForQuery["type"] = str(_typeValue_)
   valuesForQuery["keyname"] = thisSrcIp
   _fromDB_values_ = exact_findout('juniperSrx_cacheObjects', valuesForQuery)
   itemValuesList = []
   for _dictValue_ in _fromDB_values_:
      for itemValue in _dictValue_[u'values']:
         if itemValue not in itemValuesList:
           itemValuesList.append(itemValue)
   return itemValuesList

def perfectMatchProcessor(_element_, inputObject, this_processor_queue):
   #
   thisSrcIpString, thisDstIpString, thisAppProtocolString, thisSrcPortString, thisDstPortString, thisActionString = returnStringOutput(inputObject)
   # 
   perfectMatchedSrcIpList = perfectMatch_valueSearch(_element_, 'srcIp', thisSrcIpString)
   perfectMatchedDstIpList = perfectMatch_valueSearch(_element_, 'dstIp', thisDstIpString)
   perfectMatchedSrcPortList = perfectMatch_valueSearch(_element_, 'srcPort', thisSrcPortString)
   perfectMatchedDrcPortList = perfectMatch_valueSearch(_element_, 'dstPort', thisDstPortString)
   perfectMatchedActionList = perfectMatch_valueSearch(_element_, 'action', thisActionString)
   #
   perfectMatchList = interSectionLoop([perfectMatchedSrcIpList, perfectMatchedDstIpList, perfectMatchedSrcPortList, perfectMatchedDrcPortList, perfectMatchedActionList])
   #
   copiedElement = copy.copy(_element_)
   if len(perfectMatchList):
     matchStatus = int(1)
   else:
     matchStatus = int(0)
   #
   copiedElement['matchstatus'] = matchStatus
   copiedElement['matchitems'] = perfectMatchList
   #
   this_processor_queue.put(copiedElement)
   #
   time.sleep(1)

##############################################
# include match processor
##############################################
def obtainIncludeAddress(_element_, _typeValue_, thisSrcIp):
   if re.search('^all$',thisSrcIp, re.I):
     return perfectMatch_valueSearch(_element_, _typeValue_, thisSrcIp)
   else:
     valuesForQuery = copy.copy(_element_)
     valuesForQuery["type"] = str(_typeValue_)
     valuesForQuery["size"] = { '$lte':int(thisSrcIp.strip().split('/')[-1]) }
     _fromDB_values_ = exact_findout('juniperSrx_cacheObjects', valuesForQuery)
     itemValuesList = []
     for _dictValue_ in _fromDB_values_:
        _fromDB_keyvalueString_ = str(_dictValue_[u'keyname']).strip()
        if re.search('[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+/[0-9]+', _fromDB_keyvalueString_):
          if IPNetwork(thisSrcIp) in IPNetwork(_fromDB_keyvalueString_):
            for itemValue in _dictValue_[u'values']:
               if itemValue not in itemValuesList:
                 itemValuesList.append(itemValue)
     return itemValuesList 

def obtainIncludePort(_element_, _typeValue_, thisSrcIp):
   if re.search('tcp/', thisSrcIp, re.I) or re.search('udp/', thisSrcIp, re.I):
     portRangeList = str(thisSrcIp.split('/')[-1]).strip().split('-')
     startNumber = int(portRangeList[0])
     endNumber = int(portRangeList[1])
     _thisPortNumber_ = map(lambda x : x + startNumber, range(endNumber - startNumber + 1)) 
     _thisPortCount_ = len(_thisPortNumber_)
     valuesForQuery = copy.copy(_element_)
     valuesForQuery["type"] = str(_typeValue_)
     valuesForQuery["size"] = { '$gte':_thisPortCount_ }
     _fromDB_values_ = exact_findout('juniperSrx_cacheObjects', valuesForQuery)
     itemValuesList = []
     for _dictValue_ in _fromDB_values_:
        fromKeyNameString = str(_dictValue_[u'keyname']).strip()
        if re.search('tcp/', fromKeyNameString, re.I) or re.search('udp/', fromKeyNameString, re.I):
          _fromDB_portRangeList_ = str(fromKeyNameString.split('/')[-1]).strip().split('-')
          _fromDB_startNumber_ = int(_fromDB_portRangeList_[0])
          _fromDB_endNumber_ = int(_fromDB_portRangeList_[1])
          _fromDBPortNumber_ = map(lambda x : x + _fromDB_startNumber_, range(_fromDB_endNumber_ - _fromDB_startNumber_ + 1))
          _fromDBPortCount = len(_fromDBPortNumber_)
          if (len(list(set(_thisPortNumber_).intersection(_fromDBPortNumber_))) == _thisPortCount_):
            for itemValue in _dictValue_[u'values']:
               if itemValue not in itemValuesList:
                 itemValuesList.append(itemValue)
     return itemValuesList
   else: 
     return perfectMatch_valueSearch(_element_, _typeValue_, thisSrcIp)
     
def includeMatchProcessor(_element_, inputObject, this_processor_queue):
   #
   thisSrcIpString, thisDstIpString, thisAppProtocolString, thisSrcPortString, thisDstPortString, thisActionString = returnStringOutput(inputObject)
   #
   includeMatchedSrcIpList = obtainIncludeAddress(_element_, 'srcIp', thisSrcIpString)
   includeMatchedDstIpList = obtainIncludeAddress(_element_, 'dstIp', thisDstIpString)
   includeMatchedSrcPortList = obtainIncludePort(_element_, 'srcPort', thisSrcPortString)
   includeMatchedDstPortList = obtainIncludePort(_element_, 'dstPort', thisDstPortString)
   includeMatchedActionList = perfectMatch_valueSearch(_element_, 'action', thisActionString)
   #
   includedMatchList = interSectionLoop([includeMatchedSrcIpList, includeMatchedDstIpList, includeMatchedSrcPortList, includeMatchedDstPortList, includeMatchedActionList])
   #
   copiedElement = copy.copy(_element_)
   if len(includedMatchList):
     matchStatus = int(1)
   else:
     matchStatus = int(0)
   #
   copiedElement['matchstatus'] = matchStatus
   copiedElement['matchitems'] = includedMatchList 
   #
   this_processor_queue.put(copiedElement)
   #
   time.sleep(1)

######################################################################
# patial match processor
# 0.0.0.0/0 include every things, this means every object in devices.
######################################################################
def obtainPatialAddress(_element_, _typeValue_, thisSrcIp):
   if re.search('^all$',thisSrcIp, re.I) or re.search('^0.0.0.0/0$',thisSrcIp, re.I):
     return perfectMatch_valueSearch(_element_, _typeValue_, 'all')
   else:
     valuesForQuery = copy.copy(_element_)
     valuesForQuery["type"] = str(_typeValue_)
     valuesForQuery["size"] = { '$gte':int(thisSrcIp.strip().split('/')[-1]) }
     _fromDB_values_ = exact_findout('juniperSrx_cacheObjects', valuesForQuery)
     itemKeyNamesList = []
     itemValuesList = []
     for _dictValue_ in _fromDB_values_:
        _fromDB_keyvalueString_ = str(_dictValue_[u'keyname']).strip()
        if re.search('[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+/[0-9]+', _fromDB_keyvalueString_):
          if IPNetwork(_fromDB_keyvalueString_) in IPNetwork(thisSrcIp):
            if _fromDB_keyvalueString_ not in itemKeyNamesList:
              itemKeyNamesList.append(_fromDB_keyvalueString_)
            for itemValue in _dictValue_[u'values']:
               if itemValue not in itemValuesList:
                 itemValuesList.append(itemValue)
     return itemValuesList

def obtainPatialPort(_element_, _typeValue_, thisSrcIp):
   if re.search('tcp/', thisSrcIp, re.I) or re.search('udp/', thisSrcIp, re.I):
     portRangeList = str(thisSrcIp.split('/')[-1]).strip().split('-')
     startNumber = int(portRangeList[0])
     endNumber = int(portRangeList[1])
     _thisPortNumber_ = map(lambda x : x + startNumber, range(endNumber - startNumber + 1))
     _thisPortCount_ = len(_thisPortNumber_)
     valuesForQuery = copy.copy(_element_)
     valuesForQuery["type"] = str(_typeValue_)
     valuesForQuery["size"] = { '$gt':0 }
     _fromDB_values_ = exact_findout('juniperSrx_cacheObjects', valuesForQuery)
     itemValuesList = []
     for _dictValue_ in _fromDB_values_:
        fromKeyNameString = str(_dictValue_[u'keyname']).strip()
        if re.search('tcp/', fromKeyNameString, re.I) or re.search('udp/', fromKeyNameString, re.I):
          _fromDB_portRangeList_ = str(fromKeyNameString.split('/')[-1]).strip().split('-')
          _fromDB_startNumber_ = int(_fromDB_portRangeList_[0])
          _fromDB_endNumber_ = int(_fromDB_portRangeList_[1])
          _fromDBPortNumber_ = map(lambda x : x + _fromDB_startNumber_, range(_fromDB_endNumber_ - _fromDB_startNumber_ + 1))
          _fromDBPortCount = len(_fromDBPortNumber_)
          if len(list(set(_thisPortNumber_).intersection(_fromDBPortNumber_))):
            for itemValue in _dictValue_[u'values']:
               if itemValue not in itemValuesList:
                 itemValuesList.append(itemValue)
     return itemValuesList
   elif re.search('all', thisSrcIp, re.I) or re.search('0/0-65535', thisSrcIp, re.I):
     return perfectMatch_valueSearch(_element_, _typeValue_, 'all')
   else: 
     return perfectMatch_valueSearch(_element_, _typeValue_, thisSrcIp)


def obtainItemsRuleHas(_element_, partialMatchList):
   _sourceEveryNet_ = []
   _destinationEveryNet_ = []
   _sourceEveryPort_ = []
   _destinationEveryPort_ = []
   for _inersectionElement_ in partialMatchList:
      _ruleNameSeq_ = str(_inersectionElement_).strip().split('#')
      _copiedElement_ = copy.copy(_element_)
      _copiedElement_["policyname"] = _ruleNameSeq_[0]
      _copiedElement_["sequence_number"] = _ruleNameSeq_[1]
      _fromDB_values_ = exact_findout('juniperSrx_cachePolicyTable', _copiedElement_)
      for _dictValue_ in _fromDB_values_:
         #_fromDB_srcIp_ = str(_dictValue_[u'srcIp']).strip()
         #_fromDB_dstIp_ = str(_dictValue_[u'dstIp']).strip()
         #_fromDB_srcPort_ = str(_dictValue_[u'srcPort']).strip()
         #_fromDB_dstPort_ = str(_dictValue_[u'dstPort']).strip()
         for _fromDB_srcIp_ in _dictValue_[u'srcIp']:
            _stringText_ = str(_fromDB_srcIp_).strip()
            if _stringText_ not in _sourceEveryNet_:
              _sourceEveryNet_.append(_stringText_)
         for _fromDB_dstIp_ in _dictValue_[u'dstIp']:         
            _stringText_ = str(_fromDB_dstIp_).strip()
            if _stringText_ not in _destinationEveryNet_:
              _destinationEveryNet_.append(_stringText_)
         for _fromDB_srcPort_ in _dictValue_[u'srcPort']:
            _stringText_ = str(_fromDB_srcPort_).strip()
            if _stringText_ not in _sourceEveryPort_:
              _sourceEveryPort_.append(_stringText_)
         for _fromDB_dstPort_ in _dictValue_[u'dstPort']:
            _stringText_ = str(_fromDB_dstPort_).strip()
            if _stringText_ not in _destinationEveryPort_:
              _destinationEveryPort_.append(_stringText_)
   return _sourceEveryNet_, _destinationEveryNet_, _sourceEveryPort_, _destinationEveryPort_

#def partialAddressValidation(_sourceEveryNet_, thisSrcIp):
def partialAddressValidation(_sourceEveryNet_, thisSrcIp, _thisSmQueue_):    
   #if re.search('^all$',thisSrcIp, re.I) or re.search('^0.0.0.0/0$',thisSrcIp, re.I):
   if re.search('^all$',thisSrcIp, re.I): 
     #return 1
     _thisSmQueue_.put(1)
   else:
     netList = removeIncluded_netAddress(_sourceEveryNet_)
     if checkSubnetStatus(netList, thisSrcIp):
       _thisSmQueue_.put(0) 
       #return 0
     else:
       _thisSmQueue_.put(1) 
       #return 1
   #
   time.sleep(1)

#def partialPortValidation(_sourceEveryPort_, thisSrcIp):
def partialPortValidation(_sourceEveryPort_, thisSrcIp, _thisSmQueue_):
   if re.search('tcp/', thisSrcIp, re.I) or re.search('udp/', thisSrcIp, re.I):
     portRangeList = str(thisSrcIp.split('/')[-1]).strip().split('-')
     startNumber = int(portRangeList[0])
     endNumber = int(portRangeList[1])
     _thisPortNumber_ = map(lambda x : x + startNumber, range(endNumber - startNumber + 1))
     itemValuesList = []
     for _element_ in _sourceEveryPort_:
        fromKeyNameString = str(_element_).strip()
        if re.search('tcp/', fromKeyNameString, re.I) or re.search('ucp/', fromKeyNameString, re.I):
          _fromDB_portRangeList_ = str(fromKeyNameString.split('/')[-1]).strip().split('-')
          _fromDB_startNumber_ = int(_fromDB_portRangeList_[0])
          _fromDB_endNumber_ = int(_fromDB_portRangeList_[1])
          _fromDBPortNumber_ = map(lambda x : x + _fromDB_startNumber_, range(_fromDB_endNumber_ - _fromDB_startNumber_ + 1))
          itemValuesList = itemValuesList + _fromDBPortNumber_
     if len(list(set(itemValuesList).intersection(_thisPortNumber_))) == len(_thisPortNumber_):
       #return 1
       _thisSmQueue_.put(1) 
     else:
       #return 0
       _thisSmQueue_.put(0)
   elif re.search('all', thisSrcIp, re.I) or re.search('0/0-65535', thisSrcIp, re.I):
     #return 1
     _thisSmQueue_.put(1)
   else:   
     _stringText_ = str(thisSrcIp).strip()
     if _stringText_ in _sourceEveryPort_:
       #return 1
       _thisSmQueue_.put(1)
     else:
       #return 0
       _thisSmQueue_.put(0)
   #
   time.sleep(1) 
 

def patialMatchProcessor(_element_, inputObject, this_processor_queue): 
   #
   thisSrcIpString, thisDstIpString, thisAppProtocolString, thisSrcPortString, thisDstPortString, thisActionString = returnStringOutput(inputObject)
   #
   partialMatchedSrcIpList = obtainPatialAddress(_element_, 'srcIp', thisSrcIpString)
   partialMatchedDstIpList = obtainPatialAddress(_element_, 'dstIp', thisDstIpString)
   partialMatchedSrcPortList = obtainPatialPort(_element_, 'srcPort', thisSrcPortString)
   partialMatchedDstPortList = obtainPatialPort(_element_, 'dstPort', thisDstPortString)
   partialMatchedActionList = perfectMatch_valueSearch(_element_, 'action', thisActionString) 
   #
   partialMatchList = interSectionLoop([partialMatchedSrcIpList, partialMatchedDstIpList, partialMatchedSrcPortList, partialMatchedDstPortList, partialMatchedActionList])
   #
   copiedElement = copy.copy(_element_)
   if len(partialMatchList):
     _sourceEveryNet_, _destinationEveryNet_, _sourceEveryPort_, _destinationEveryPort_ = obtainItemsRuleHas(_element_, partialMatchList)
     #copiedElement['matchstatus'] = partialAddressValidation(_sourceEveryNet_, thisSrcIpString) & partialAddressValidation(_destinationEveryNet_, thisDstIpString) & partialPortValidation(_sourceEveryPort_, thisSrcPortString) & partialPortValidation(_destinationEveryPort_, thisDstPortString)
    
     runProcessFunctionList = [
         {'functionName':partialAddressValidation, 'argList':_sourceEveryNet_, 'argString':thisSrcIpString},
         {'functionName':partialAddressValidation, 'argList':_destinationEveryNet_, 'argString':thisDstIpString},
         {'functionName':partialPortValidation, 'argList':_sourceEveryPort_, 'argString':thisSrcPortString},
         {'functionName':partialPortValidation, 'argList':_destinationEveryPort_, 'argString':thisDstPortString}
     ]
     smallProcessQueueList = []
     for _smElement_ in runProcessFunctionList:
        smallProcessQueueList.append(Queue(maxsize=0))
     count = 0
     smallProcessList = []
     for _smElement_ in runProcessFunctionList:
        _thisSmQueue_ = smallProcessQueueList[count]
        _smProcessor_ = Process(target = _smElement_['functionName'], args = (_smElement_['argList'], _smElement_['argString'], _thisSmQueue_,))
        _smProcessor_.start()
        smallProcessList.append(_smProcessor_)
        count = count + 1
     for _smProcessor_ in smallProcessList:
        _smProcessor_.join()
     matchingBit = 1   
     for _smQueue_ in smallProcessQueueList:
        while not _smQueue_.empty():
             matchingBit = matchingBit & int(_smQueue_.get())
     #
     copiedElement['matchstatus'] = matchingBit
     #
   else:
     copiedElement['matchstatus'] = 0
   copiedElement['matchitems'] = partialMatchList  
   #
   this_processor_queue.put(copiedElement)
   #
   time.sleep(1)  


def convertDictFromMatched(_returnOutputMemory_, statusAfterPerfectMatchProcessor, _dictForKeyName_):
   for _dictionaryElement_ in statusAfterPerfectMatchProcessor:
      _keyName_ = "%(hostname)s %(from_zone)s %(to_zone)s" % _dictionaryElement_
      #
      if _keyName_ not in _returnOutputMemory_:
        _returnOutputMemory_[_keyName_] = {}
      #
      if _dictForKeyName_ not in _returnOutputMemory_[_keyName_].keys(): 
        _returnOutputMemory_[_keyName_][_dictForKeyName_] = {}
        _returnOutputMemory_[_keyName_][_dictForKeyName_]['matchstatus'] = 0
        _returnOutputMemory_[_keyName_][_dictForKeyName_]['matchitems'] = []
        _returnOutputMemory_[_keyName_][_dictForKeyName_]['policyrules'] = []
      #
      _keyNameByHostName_ = _returnOutputMemory_[_keyName_].keys()
      #
      _returnOutputMemory_[_keyName_][_dictForKeyName_]['matchstatus'] = _dictionaryElement_['matchstatus']
      _exceptListSum_ = []
      for _matchKeyName_ in _keyNameByHostName_:
         if not re.search(_dictForKeyName_, _matchKeyName_, re.I):
           _exceptListSum_ = _exceptListSum_ + _returnOutputMemory_[_keyName_][_matchKeyName_]['matchitems']
      for _uniqueElement_ in _dictionaryElement_['matchitems']:
         if _uniqueElement_ not in _exceptListSum_:
           _returnOutputMemory_[_keyName_][_dictForKeyName_]['matchitems'].append(_uniqueElement_)
      #
      _sortingBox_ = {}
      for _uniqueElement_ in _returnOutputMemory_[_keyName_][_dictForKeyName_]['matchitems']:
         _splitedElement_ = str(_uniqueElement_).strip().split('#')
         _insertQuery_ = {
                             'policyname': _splitedElement_[0],
                             'sequence_number': _splitedElement_[1],
                             'hostname': _dictionaryElement_['hostname'],
                             'from_zone': _dictionaryElement_['from_zone'],
                             'to_zone': _dictionaryElement_['to_zone']
                         }
         _fromDB_values_ = exact_findout('juniperSrx_cachePolicyTable', _insertQuery_)
         for _dbElement_ in _fromDB_values_:
            _copiedElement_ = copy.copy(_dbElement_)
            _seqNumber_ = int(_copiedElement_[u'sequence_number'])
            if _seqNumber_ not in _sortingBox_.keys():
              _sortingBox_[_seqNumber_] = {}
            del _copiedElement_[u'_id']
            _sortingBox_[_seqNumber_] = _copiedElement_
      #
      _indexNumber_ = _sortingBox_.keys()
      _indexNumber_.sort()
      _outValuseList_ = []
      for _Number_ in _indexNumber_:
         _outValuseList_.append(_sortingBox_[_Number_])
      _returnOutputMemory_[_keyName_][_dictForKeyName_]['policyrules'] = _outValuseList_
   return _returnOutputMemory_


@api_view(['POST'])
@csrf_exempt
def juniper_searchpolicy(request,format=None):

   #global tatalsearched_values, threadlock_key
   #threadlock_key = threading.Lock()
   #tatalsearched_values = []

   # get method
   #if request.method == 'GET':
   #  parameter_from = request.query_params.dict()



   if request.method == 'POST':
   #elif request.method == 'POST':
       _input_ = JSONParser().parse(request)

       #
       _fromDB_values_ = exact_findout('juniperSrx_devicesInfomation', {"failover" : "primary"})
       primaryHostNames = []
       for _dictValue_ in _fromDB_values_:
          _hostName_ = str(_dictValue_[u'hostname'])
          if _hostName_ not in primaryHostNames:
            primaryHostNames.append(_hostName_)
       
       #device_information_values = obtainjson_from_mongodb('juniper_srx_devices')
       #primary_devices = findout_primary_devices(device_information_values)

       # confirm input type 
       if type(_input_) != type({}):
         return_object = {
              "items":[],
              "process_status":"error",
              "process_msg":"input wrong format"
         }
         return Response(json.dumps(return_object))

       if ('items' in _input_.keys()) and (u'items' in _input_.keys()):
         inputObjectList = _input_[u'items'] 
         if len(inputObjectList) == 1:
           #
           inputObject = inputObjectList[0]

           ##############################################
           # choose the firewall and zone               #
           ##############################################
           startTime = time.time()
           print "start searching zone and devices processing"  
           processing_queues_list = []
           for _element_ in primaryHostNames:
              processing_queues_list.append(Queue(maxsize=0))
           #
           count = 0
           _processor_list_ = []
           for _element_ in primaryHostNames:
              this_processor_queue = processing_queues_list[count]
              _processor_ = Process(target = findOut_fwAndZone, args = (_element_, inputObject, this_processor_queue,))
              _processor_.start()
              _processor_list_.append(_processor_)
              count = count + 1
           for _processor_ in _processor_list_:
              _processor_.join()

           # fwAndZone_selectedList : [{'to_zone': 'PRI', 'from_zone': 'COM', 'hostname': 'KRIS10-PUBF02-5400FW'}]
           fwAndZone_selectedList = []
           for _queue_ in processing_queues_list:
              while not _queue_.empty():
                       fwAndZone_selectedList.append(_queue_.get())

           endTime = time.time()
           timeGapString = str(int(endTime - startTime))
           print "include matching done. %(timeGapString)s seconds spent" % {'timeGapString':timeGapString}
           ##############################################
           # perfect match                              #
           ##############################################
           startTime = time.time()
           print "start perfect matching processing"
           processing_queues_list = []
           for _element_ in fwAndZone_selectedList:
              processing_queues_list.append(Queue(maxsize=0)) 
           #
           count = 0
           _processor_list_ = []
           for _element_ in fwAndZone_selectedList:
              this_processor_queue = processing_queues_list[count]
              _processor_ = Process(target = perfectMatchProcessor, args = (_element_, inputObject, this_processor_queue,))
              _processor_.start()
              _processor_list_.append(_processor_)
              count = count + 1
           for _processor_ in _processor_list_:
              _processor_.join()
           
           #
           statusAfterPerfectMatchProcessor = []
           for _queue_ in processing_queues_list:
              while not _queue_.empty():
                       statusAfterPerfectMatchProcessor.append(_queue_.get())
                    
           endTime = time.time()
           timeGapString = str(int(endTime - startTime))
           print "perfect matching done. %(timeGapString)s seconds spent" % {'timeGapString':timeGapString}
           ##############################################
           # include match                              #
           ##############################################
           startTime = time.time() 
           print "start include matching processing"
           processing_queues_list = []
           for _element_ in fwAndZone_selectedList:
              processing_queues_list.append(Queue(maxsize=0))
           #
           count = 0
           _processor_list_ = []
           for _element_ in fwAndZone_selectedList:
              this_processor_queue = processing_queues_list[count]
              _processor_ = Process(target = includeMatchProcessor, args = (_element_, inputObject, this_processor_queue,))
              _processor_.start()
              _processor_list_.append(_processor_)
              count = count + 1
           for _processor_ in _processor_list_:
              _processor_.join()

           #
           statusAfterIncludeMatchProcessor = []
           for _queue_ in processing_queues_list:
              while not _queue_.empty():
                       statusAfterIncludeMatchProcessor.append(_queue_.get())
                        
           endTime = time.time()
           timeGapString = str(int(endTime - startTime))
           print "include matching done. %(timeGapString)s seconds spent" % {'timeGapString':timeGapString}
           ##############################################
           # partial match                              #
           ##############################################
           startTime = time.time() 
           print "start partial matching processing"
           processing_queues_list = []
           for _element_ in fwAndZone_selectedList:
              processing_queues_list.append(Queue(maxsize=0))
           #
           count = 0
           _processor_list_ = []
           for _element_ in fwAndZone_selectedList:
              this_processor_queue = processing_queues_list[count]
              _processor_ = Process(target = patialMatchProcessor, args = (_element_, inputObject, this_processor_queue,))
              _processor_.start()
              _processor_list_.append(_processor_)
              count = count + 1
           for _processor_ in _processor_list_:
              _processor_.join()
           #
           statusAfterPartialMatchProcessor = []
           for _queue_ in processing_queues_list:
              while not _queue_.empty():
                       statusAfterPartialMatchProcessor.append(_queue_.get())

           endTime = time.time()
           timeGapString = str(int(endTime - startTime))
           print "partial matching done. %(timeGapString)s seconds spent" % {'timeGapString':timeGapString}              
           ##############################################
           # combine and summary                        # 
           ##############################################
           startTime = time.time()
           print "start information re-organization processing"
           _returnOutputMemory_ = {}
           _returnOutputMemory_ = convertDictFromMatched(_returnOutputMemory_, statusAfterPerfectMatchProcessor, 'perfect')
           _returnOutputMemory_ = convertDictFromMatched(_returnOutputMemory_, statusAfterIncludeMatchProcessor, 'include')
           _returnOutputMemory_ = convertDictFromMatched(_returnOutputMemory_, statusAfterPartialMatchProcessor, 'partial')
           endTime = time.time()
           timeGapString = str(int(endTime - startTime))
           print "information re-organization done. %(timeGapString)s seconds spent" % {'timeGapString':timeGapString}
           ##############################################
           # analysis                                   #
           ##############################################
           startTime = time.time()
           print "start analysis processing" 
           returnitems = []
           _hostNameZoneName_ = _returnOutputMemory_.keys() 
           for _keyName_ in _hostNameZoneName_:
              #
              _PFMS_ = _returnOutputMemory_[_keyName_]['perfect']['matchstatus']
              _INMS_ = _returnOutputMemory_[_keyName_]['include']['matchstatus']
              _PTMS_ = _returnOutputMemory_[_keyName_]['partial']['matchstatus']
              finalMatchStatus = 0
              if (_PFMS_ | _INMS_):
                finalMatchStatus = 1
              else:
                if _PTMS_:
                  finalMatchStatus = 1
                else:
                  finalMatchStatus = 0
              #
              splited_keyName = str(_keyName_).strip().split()
              #
              returnOutputDict = {
                'hostname':splited_keyName[0],
                'from_zone':splited_keyName[1],
                'to_zone':splited_keyName[2],
                'matchstatus':finalMatchStatus,
                'perfectrules':_returnOutputMemory_[_keyName_]['perfect']['policyrules'],
                'includerules':_returnOutputMemory_[_keyName_]['include']['policyrules'],
                'partialrules':_returnOutputMemory_[_keyName_]['partial']['policyrules']
              }
              returnitems.append(returnOutputDict)
           #
           endTime = time.time()
           timeGapString = str(int(endTime - startTime))
           print "analysis done. %(timeGapString)s seconds spent" % {'timeGapString':timeGapString} 
           return_object = {
                  "items":returnitems,
                  "process_status":"done",
                  "process_msg":"done"
           }
           return Response(json.dumps(return_object))
           #
         else:
           return_object = {
                  "items":[],
                  "process_status":"error",
                  "process_msg":"not single item for searching"
           }
           return Response(json.dumps(return_object))
       else:
         return_object = {
                "items":[],
                "process_status":"error",
                "process_msg":"no items in input"
         }
         return Response(json.dumps(return_object))


