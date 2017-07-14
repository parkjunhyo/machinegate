
USER_JUNIPER_DIR = "/home/1002391/machinegate/juniperapi/"

USER_VAR_POLICIES = USER_JUNIPER_DIR + "var/policies/"

USER_VAR_CHCHES = USER_JUNIPER_DIR + "var/caches/"

USER_VAR_NAT = USER_JUNIPER_DIR + "var/nat/"

#USER_DATABASES_DIR = USER_JUNIPER_DIR + "databases/"

USER_VAR_ROUTING = USER_JUNIPER_DIR + "var/routing/"

USER_VAR_INTERFACES = USER_JUNIPER_DIR + "var/interfaces/"

USER_VAR_ADDRESSBOOK = USER_JUNIPER_DIR + "var/addressbook/"

USER_VAR_APPLICATIONS = USER_JUNIPER_DIR + "var/applications/"

USER_NAME = "admin"
	
USER_PASSWORD = "Skplanet03!"

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
 "ip":'192.168.56.101',
 "port":'61700',
 "dbname":'juniperSrx',
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
