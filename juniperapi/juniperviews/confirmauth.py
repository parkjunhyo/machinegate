from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.renderers import JSONRenderer
from rest_framework.parsers import JSONParser

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils.six import BytesIO

#from juniperapi.setting import USER_DATABASES_DIR
#from juniperapi.setting import USER_NAME
#from juniperapi.setting import USER_PASSWORD
from juniperapi.setting import ENCAP_PASSWORD
from juniperapi.setting import system_property 

import re, json

class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders its content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)

@api_view(['POST'])
@csrf_exempt
def confirmauth(request,format=None):


   if request.method == 'POST':
     if not re.search(r"^system$", system_property["role"], re.I):
       return_output = {
         "items":[],
         "process_status":"error",
         "process_msg":"this application does not have admin role!"
       }
       return Response(json.dumps(return_output))
    
     _input_ = JSONParser().parse(request)
     if u'auth_password' not in _input_:
       return_output = {
         "items":[],
         "process_status":"error",
         "process_msg":"no auth_password"
       }
       return Response(json.dumps(return_output))
     else:
       if re.match(ENCAP_PASSWORD, str(_input_[u'auth_password'])):
         return_output = {
           "items":[_input_],
           "process_status":"done",
           "process_msg":"auth_password"
         }
         return Response(json.dumps(return_output))
       else:
         return_output = {
           "items":[],
           "process_status":"error",
           "process_msg":"wrong auth_password"
         }
         return Response(json.dumps(return_output))

     # if re.search(r"system", system_property["role"], re.I):
     #   _input_ = JSONParser().parse(request)
     #   # confirm input type 
     #   if type(_input_) != type({}):
     #     return_object = {"items":[{"message":"input should be object or dictionary!!","process_status":"error"}]}
     #     return Response(json.dumps(return_object))
     #   # confirm auth
     #   if ('auth_key' not in _input_.keys()) and (u'auth_key' not in _input_.keys()):
     #     return_object = {"items":[{"message":"no authorization!","process_status":"error"}]}
     #     return Response(json.dumps(return_object))
     #   # 
     #   auth_matched = re.match(ENCAP_PASSWORD, _input_['auth_key'])
     #   if auth_matched:
     #     if ('items' in _input_.keys()) and (u'items' in _input_.keys()):
     #       return_result = {}
     #       # from database
     #       registered_info_from_mongodb = obtainjson_from_mongodb(mongo_db_collection_name)
     #       #
     #       registered_ip_string = []
     #       registered_ip_unicode = []
     #       for _dictvalues_ in registered_info_from_mongodb:
     #          registered_ip_string.append(str(_dictvalues_[u'apiaccessip']))
     #          registered_ip_unicode.append(_dictvalues_[u'apiaccessip'])
     #       # queue generation
     #       processing_queues_list = []
     #       for dataDict_value in _input_[u'items']:
     #          processing_queues_list.append(Queue(maxsize=0))
     #       # run processing to get information
     #       count = 0
     #       _processor_list_ = []
     #       for dataDict_value in _input_[u'items']:
     #          this_processor_queue = processing_queues_list[count]
     #          _processor_ = Process(target = confirm_ip_reachable, args = (dataDict_value, this_processor_queue, registered_ip_string, registered_ip_unicode, mongo_db_collection_name,))
     #          _processor_.start()
     #          _processor_list_.append(_processor_)
     #          # for next queue
     #          count = count + 1
     #       for _processor_ in _processor_list_:
     #          _processor_.join()
     #       # get information from the queue
     #       search_result = []
     #       for _queue_ in processing_queues_list:
     #          while not _queue_.empty():
     #               _get_values_ = _queue_.get()
     #               search_result.append(_get_values_)
     #       #
     #       return Response(json.dumps({"items":search_result}))
     #     # end of if ('items' in _input_.keys()) and (u'items' in _input_.keys()):
     #     else:
     #       return_object = {"items":[{"message":"no items for request!","process_status":"error"}]}
     #       return Response(json.dumps(return_object))
     #   # end of if auth_matched:
     #   else:
     #     return_object = {"items":[{"message":"no authorization!","process_status":"error"}]}
     #     return Response(json.dumps(return_object))
     # # end of if re.search(r"system", system_property["role"], re.I):
     # else:
     #   return_object = {"items":[{"message":"this host has no authorizaition!","process_status":"error"}]}
     #   return Response(json.dumps(return_object))

