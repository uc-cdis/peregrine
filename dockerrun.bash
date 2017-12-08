#!/bin/bash

cd /var/www/peregrine
python wsgi.py
uwsgi --ini /etc/uwsgi/uwsgi.ini &
nginx -g 'daemon off;'
