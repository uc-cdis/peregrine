ARG AZLINUX_BASE_VERSION=feat_python3.13-alias

# FROM quay.io/cdis/python-nginx-al:${AZLINUX_BASE_VERSION} AS base
FROM quay.io/cdis/python-build-base:feat_python3.13-alias AS base


ENV appname=peregrine

WORKDIR /${appname}

RUN useradd -m -s /bin/bash gen3
RUN chown -R gen3:gen3 /${appname}

# Builder stage
FROM base AS builder

RUN dnf install -y python3-devel postgresql-devel gcc
RUN pip install poetry

RUN chown -R gen3:gen3 /venv

USER gen3
WORKDIR /${appname}

# copy ONLY poetry artifact, install the dependencies but not the app;
# this will make sure that the dependencies are cached

COPY poetry.lock pyproject.toml /${appname}/
RUN poetry install -vv --no-root --only main --no-interaction

COPY --chown=gen3:gen3 . /${appname}



# install the app
RUN poetry install --without dev --no-interaction

RUN git config --global --add safe.directory ${appname} && COMMIT=`git rev-parse HEAD` && echo "COMMIT=\"${COMMIT}\"" > ${appname}/version_data.py \
    && VERSION=`git describe --always --tags` && echo "VERSION=\"${VERSION}\"" >> ${appname}/version_data.py

# Final stage
FROM base

RUN  yum install -y postgresql-libs

COPY --from=builder /${appname} /${appname}

# Switch to non-root user 'gen3' for the serving process
USER gen3

WORKDIR /${appname}

CMD ["/bin/bash", "-c", "/${appname}/dockerrun.bash"]
