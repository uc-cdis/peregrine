ARG AZLINUX_BASE_VERSION=3.13-pythonnginx

FROM quay.io/cdis/amazonlinux-base:${AZLINUX_BASE_VERSION} AS base

ENV appname=peregrine

WORKDIR /${appname}

RUN chown -R gen3:gen3 /${appname}

# Builder stage
FROM base AS builder

USER root
RUN dnf install -y python3-devel postgresql-devel gcc

USER gen3

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

USER root
RUN  yum install -y postgresql-libs

COPY --from=builder /${appname} /${appname}


# Create the log directory and log files
RUN mkdir -p /var/log/nginx \
    && touch /var/log/nginx/access.log /var/log/nginx/error.log \
    && chown -R gen3:gen3 /var/log/nginx \
    && chmod -R 664 /var/log/nginx/*.log \
    && ln -sf /dev/stdout /var/log/nginx/access.log \
    && ln -sf /dev/stderr /var/log/nginx/error.log

# Switch to non-root user 'gen3' for the serving process
USER gen3

# Install into existing venv
ENV VIRTUAL_ENV=/venv
ENV PATH="/venv/bin:/usr/sbin:${PATH}"
ENV POETRY_VIRTUALENVS_CREATE=false

WORKDIR /${appname}

# install the app
RUN poetry install --without dev --no-interaction

CMD ["/bin/bash", "-c", "/${appname}/dockerrun.bash"]
