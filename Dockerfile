# To run: docker run -v /path/to/wsgi.py:/var/www/peregrine/wsgi.py --name=peregrine -p 81:80 peregrine
# To check running container: docker exec -it peregrine /bin/bash

FROM quay.io/cdis/python-nginx:pybase3-1.6.2

ENV appname=peregrine

RUN apk update \
    && apk add postgresql-libs postgresql-dev libffi-dev libressl-dev \
    && apk add alpine-sdk linux-headers musl-dev gcc libxml2-dev libxslt-dev \
    && apk add curl bash git vim

# install poetry
RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python

COPY . /$appname
COPY ./deployment/uwsgi/uwsgi.ini /etc/uwsgi/uwsgi.ini
WORKDIR /$appname

# cache so that poetry install will run if these files change
COPY poetry.lock pyproject.toml /$appname/

# install Fence and dependencies via poetry
RUN source $HOME/.poetry/env \
    && poetry config virtualenvs.create false \
    && poetry install -vv --no-dev --no-interaction \
    && poetry show -v

RUN mkdir -p /var/www/$appname \
    && mkdir -p /var/www/.cache/Python-Eggs/ \
    && mkdir /run/nginx/ \
    && ln -sf /dev/stdout /var/log/nginx/access.log \
    && ln -sf /dev/stderr /var/log/nginx/error.log \
    && chown nginx -R /var/www/.cache/Python-Eggs/ \
    && chown nginx /var/www/$appname

EXPOSE 80

RUN COMMIT=`git rev-parse HEAD` && echo "COMMIT=\"${COMMIT}\"" >$appname/version_data.py \
    && VERSION=`git describe --always --tags` && echo "VERSION=\"${VERSION}\"" >>$appname/version_data.py

WORKDIR /var/www/$appname

CMD /dockerrun.sh
