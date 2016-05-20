#! /usr/bin/env bash

PORT=$(cat f5restapi/setting.py | grep -i 'RUNSERVER_PORT' | awk -F"[ ']" '{print $4}')

python manage.py runserver 0.0.0.0:$PORT




