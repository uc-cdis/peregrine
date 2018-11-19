# To run: docker run -v /path/to/wsgi.py:/var/www/peregrine/wsgi.py --name=peregrine -p 81:80 peregrine
# To check running container: docker exec -it peregrine /bin/bash

FROM ubuntu:16.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    # dependency for cryptography
    libffi-dev \
    # dependency for pyscopg2 - which is dependency for sqlalchemy postgres engine
    libpq-dev \
    # dependency for cryptography
    libssl-dev \
    libxml2-dev \
    libxslt1-dev \
    nginx \
    python2.7 \
    python-dev \
    python-pip \
    python-setuptools \
    sudo \
    vim \
    && python -m pip install --upgrade pip \
    && python -m pip install --upgrade setuptools \
    && python -m pip install --upgrade uwsgi \
    && mkdir /var/www/peregrine \
    && mkdir -p /var/www/.cache/Python-Eggs/ \
    && chown www-data -R /var/www/.cache/Python-Eggs/ \
    && mkdir /run/nginx/

COPY . /peregrine
COPY ./deployment/uwsgi/uwsgi.ini /etc/uwsgi/uwsgi.ini
COPY ./deployment/nginx/nginx.conf /etc/nginx/
COPY ./deployment/nginx/uwsgi.conf /etc/nginx/sites-available/
WORKDIR /peregrine

RUN pip install -r requirements.txt \
    && COMMIT=`git rev-parse HEAD` && echo "COMMIT=\"${COMMIT}\"" >peregrine/version_data.py \
    && VERSION=`git describe --always --tags` && echo "VERSION=\"${VERSION}\"" >>peregrine/version_data.py \
    && cd /peregrine/src/gdcdictionary && DICTCOMMIT=`git rev-parse HEAD` && echo "DICTCOMMIT=\"${DICTCOMMIT}\"" >>/peregrine/peregrine/version_data.py \
    && DICTVERSION=`git describe --always --tags` && echo "DICTVERSION=\"${DICTVERSION}\"" >>/peregrine/peregrine/version_data.py \
    && python setup.py install \
    && rm /etc/nginx/sites-enabled/default \
    && ln -s /etc/nginx/sites-available/uwsgi.conf /etc/nginx/sites-enabled/uwsgi.conf \
    && ln -sf /dev/stdout /var/log/nginx/access.log \
    && ln -sf /dev/stderr /var/log/nginx/error.log \
    && chown www-data /var/www/peregrine

EXPOSE 80

WORKDIR /var/www/peregrine

ENTRYPOINT [ "/bin/sh", "/peregrine/dockerrun.sh" ]
CMD []
