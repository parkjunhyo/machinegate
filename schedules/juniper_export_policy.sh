#! /usr/bin/env bash

JUNIPER_PATH=$(find / -name 'juniperapi' 2>&1 | grep -v 'Permission denied')

SETTING_DIR=$JUNIPER_PATH/setting.py

ENCAP_PASSWORD=$(cat $SETTING_DIR | grep -i 'ENCAP_PASSWORD = ' | awk -F "[\"]" '{print $2}')
RUNSERVER_PORT=$(cat $SETTING_DIR | grep -i 'RUNSERVER_PORT = ' | awk -F "[']" '{print $2}')

curl -H "Accept: application/json" -X POST -d "[{\"auth_key\":\"$ENCAP_PASSWORD\"}]" http://localhost:$RUNSERVER_PORT/juniper/exportpolicy/ > /dev/null

