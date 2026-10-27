#!/bin/bash

nginx
exec gunicorn -c /peregrine/deployment/wsgi/gunicorn.conf.py
