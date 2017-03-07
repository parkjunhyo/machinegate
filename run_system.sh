#! /usr/bin/env bash

SRV_LISTEN_IP='192.168.56.102'
SRV_LISTEN_PORT='8080'

python manage.py runserver $SRV_LISTEN_IP:$SRV_LISTEN_PORT




