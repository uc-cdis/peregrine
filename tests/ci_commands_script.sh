#!/usr/bin/env bash

# Set up database
poetry run python bin/setup_test_database.py
mkdir -p tests/resources/keys; cd tests/resources/keys; openssl genrsa -out test_private_key.pem 2048; openssl rsa -in test_private_key.pem -pubout -out test_public_key.pem; cd -

# run tests
poetry run pytest -vv --cov=peregrine --cov-report xml tests
