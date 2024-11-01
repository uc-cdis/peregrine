#!/bin/bash

nginx
poetry run gunicorn -c /peregrine/deployment/wsgi/gunicorn.conf.py
