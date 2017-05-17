#
https://github.com/ottoyiu/django-cors-headers
#
sudo apt-get install build-essential libssl-dev libffi-dev python-dev
#
pip install Django
pip install djangorestframework
pip install markdown
pip install django-filter
#
pip install paramiko
pip install netaddr
#
pip install django-cors-headers
#
pip install py-radix
# https://pypi.python.org/pypi/py-radix

# mongo db -usage-
db.createUser({user: "adminuser", pwd: "adminuser", roles: [{role:"userAdminAnyDatabase"}]});
db.createUser({user:'nwenguser',pwd:'nwenguser',roles:[{role:'readWrite', db:'f5_bigip'}]});
db.createUser({user:'nwenguser',pwd:'nwenguser',roles:[{role:'readWrite', db:'juniper_srx'}]});
mongo localhost:38390/juniper_srx -u 'nwenguser' -p 'nwenguser'
mongo localhost:38390/testdb -u 'adminuser' -p 'adminuser'


------------------------ 보안동작하는 코드 -----------------------
import pymongo
from bson.json_util import dumps, loads
connection = pymongo.MongoClient("10.10.10.2",38390)
connection.juniper_srx.authenticate("nwenguser","nwenguser")
mydb = connection.juniper_srx
testcollection = testdb.juniper_srx_devices
json_string = dumps(testcollection.find())
loads(json_string)



---------------- mongdo 설정 -----------------

root@server02:~# vi /etc/mongodb.conf 

# mongodb.conf

# Where to store the data.
dbpath=/var/lib/mongodb

#where to log
logpath=/var/log/mongodb/mongodb.log

logappend=true

bind_ip = 0.0.0.0
port = 38390

# Enable journaling, http://www.mongodb.org/display/DOCS/Journaling
journal=true

# Enables periodic logging of CPU utilization and I/O wait
#cpu = true

# Turn on/off security.  Off is currently the default
#noauth = true
auth = true



