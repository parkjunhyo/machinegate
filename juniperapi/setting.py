
USER_JUNIPER_DIR = "/home/1002391/machinegate/juniperapi/"

USER_VAR_POLICIES = USER_JUNIPER_DIR + "var/policies/"

USER_VAR_CHCHES = USER_JUNIPER_DIR + "var/caches/"

USER_VAR_NAT = USER_JUNIPER_DIR + "var/nat/"

USER_DATABASES_DIR = USER_JUNIPER_DIR + "databases/"

USER_NAME = "j1002391"
	
USER_PASSWORD = "Start@1jhyo"

ENCAP_PASSWORD = "Adfakladjfqern@sdfjlaf1!"

PARAMIKO_DEFAULT_TIMEWAIT = 5

RUNSERVER_PORT = '8080'

POLICY_FILE_MAX = 300

PYTHON_MULTI_PROCESS = 300

PYTHON_MULTI_THREAD = 2

## System Role
system_property = {
 # system only : post allowed
 "role":"system"
}

## MongoDB information
mongodb = {
 "ip":'10.10.10.2',
 "port":'38390',
 "dbname":'juniper_srx',
 "username":'nwenguser',
 "password":'nwenguser'
}

# Paramiko information
paramiko_conf = {
 "output_wait_timeout":0.1,
 # x output_wait_timeout : 6000 (600 seconds = 10 minutes)
 "max_wait_timeout_count":6000,
 "connect_timeout":60,
}
