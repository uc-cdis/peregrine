# Peregrine

[![Build Status](https://travis-ci.org/uc-cdis/peregrine.svg?branch=master)](https://travis-ci.org/uc-cdis/peregrine)
[![Coverage Status](https://coveralls.io/repos/github/uc-cdis/peregrine/badge.svg)](https://coveralls.io/github/uc-cdis/peregrine)

Query interface to get insights into data in Gen3 Commons

## API Documentation

[OpenAPI documentation available here.](http://petstore.swagger.io/?url=https://raw.githubusercontent.com/uc-cdis/peregrine/master/openapis/swagger.yaml)

YAML file for the OpenAPI documentation is found in the `openapi` folder (in
the root directory); see the README in that folder for more details.

## Developer Setup

### Run

```bash
poetry install
./run.py
```

### Test

```bash
python bin/setup_test_database.py --host postgres
mkdir -p tests/resources/keys; cd tests/resources/keys; openssl genrsa -out test_private_key.pem 2048; openssl rsa -in test_private_key.pem -pubout -out test_public_key.pem; cd -
```

If needed, set environment variables to point to a specific Postgres instance.

```bash
export GDC_PG_HOST=postgres
export GDC_PG_USER=postgres
export GDC_PG_PASSWORD=""
```

Run tests.

```bash
poetry run pytest -vv --cov=peregrine --cov-report xml tests
```


### Quickstart with Helm

You can now deploy individual services via Helm! 
Please refer to the Helm quickstart guide HERE (https://github.com/uc-cdis/peregrine/blob/master/docs/quickstart_helm.md)
