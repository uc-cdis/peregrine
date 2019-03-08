# To run: docker run -v /path/to/wsgi.py:/var/www/peregrine/wsgi.py --name=peregrine -p 81:80 peregrine
# To check running container: docker exec -it peregrine /bin/bash 

FROM quay.io/cdis/py27base:pybase2-1.0.0

ENV DEBIAN_FRONTEND=noninteractive

RUN mkdir /var/www/peregrine \
    && chown www-data /var/www/peregrine

COPY . /peregrine
COPY ./deployment/uwsgi/uwsgi.ini /etc/uwsgi/uwsgi.ini
WORKDIR /peregrine

RUN pip install -r requirements.txt \
    && COMMIT=`git rev-parse HEAD` && echo "COMMIT=\"${COMMIT}\"" >peregrine/version_data.py \
    && VERSION=`git describe --always --tags` && echo "VERSION=\"${VERSION}\"" >>peregrine/version_data.py \
    && cd /peregrine/src/gdcdictionary && DICTCOMMIT=`git rev-parse HEAD` && echo "DICTCOMMIT=\"${DICTCOMMIT}\"" >>/peregrine/peregrine/version_data.py \
    && DICTVERSION=`git describe --always --tags` && echo "DICTVERSION=\"${DICTVERSION}\"" >>/peregrine/peregrine/version_data.py \
    && python setup.py install

EXPOSE 80

WORKDIR /var/www/peregrine 

ENTRYPOINT [ "/bin/sh", "/dockerrun.sh" ]
CMD []
