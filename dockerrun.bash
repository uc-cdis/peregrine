#!/bin/bash

nginx
gunicorn -c /peregrine/deployment/wsgi/gunicorn.conf.py
