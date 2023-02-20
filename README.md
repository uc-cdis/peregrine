# Peregrine

[![Build Status](https://travis-ci.org/uc-cdis/peregrine.svg?branch=master)](https://travis-ci.org/uc-cdis/peregrine)
[![Codacy Badge](https://api.codacy.com/project/badge/Grade/f6128183864d4e5da5093eb72a3c9c97)](https://www.codacy.com/app/uc-cdis/peregrine?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=uc-cdis/peregrine&amp;utm_campaign=Badge_Grade)
[![Codacy Badge](https://api.codacy.com/project/badge/Coverage/f6128183864d4e5da5093eb72a3c9c97)](https://www.codacy.com/app/uc-cdis/peregrine?utm_source=github.com&utm_medium=referral&utm_content=uc-cdis/peregrine&utm_campaign=Badge_Coverage)

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

If you are looking to deploy all Gen3 services, that can be done via the Gen3 Helm chart. 
Instructions for deploying all Gen3 services with Helm can be found [here](https://github.com/uc-cdis/gen3-helm#readme).

To deploy the peregrine service:
```bash
helm repo add gen3 https://helm.gen3.org
helm repo update
helm upgrade --install gen3/peregrine
```
These commands will add the Gen3 helm chart repo and install the peregrine service to your Kubernetes cluster. 

Deploying peregrine this way will use the defaults that are defined in this [values.yaml file](https://github.com/uc-cdis/gen3-helm/blob/master/helm/peregrine/values.yaml)
You can learn more about these values by accessing the peregrine [README.md](https://github.com/uc-cdis/gen3-helm/blob/master/helm/peregrine/README.md)

If you would like to override any of the default values, simply copy the above values.yaml file into a local file and make any changes needed. 

To deploy the service independant of other services (for testing purposes), you can set the .postgres.separate value to "true". This will deploy the service with its own instance of Postgres:
```bash
  postgres:
    separate: true
```

You can then supply your new values file with the following command: 
```bash
helm upgrade --install gen3/peregrine -f values.yaml
```

If you are using Docker Build to create new images for testing, you can deploy them via Helm by replacing the .image.repository value with the name of your local image. 
You will also want to set the .image.pullPolicy to "never" so kubernetes will look locally for your image. 
Here is an example:
```bash
image:
  repository: <image name from docker image ls>
  pullPolicy: Never
  # Overrides the image tag whose default is the chart appVersion.
  tag: ""
```

Re-run the following command to update your helm deployment to use the new image: 
```bash
helm upgrade --install gen3/peregrine
```

You can also store your images in a local registry. Kind and Minikube are popular for their local registries:
- https://kind.sigs.k8s.io/docs/user/local-registry/
- https://minikube.sigs.k8s.io/docs/handbook/registry/#enabling-insecure-registries
