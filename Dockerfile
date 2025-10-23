ARG AZLINUX_BASE_VERSION=master

FROM quay.io/cdis/python-nginx-al:${AZLINUX_BASE_VERSION} AS base

ENV appname=peregrine

WORKDIR /${appname}

RUN chown -R gen3:gen3 /${appname}

# Builder stage
FROM base AS builder

RUN dnf install -y python3-devel postgresql-devel gcc

USER gen3

# copy ONLY poetry artifact, install the dependencies but not the app;
# this will make sure that the dependencies are cached
COPY poetry.lock pyproject.toml /${appname}/
RUN poetry install -vv --no-root --only main --no-interaction

COPY --chown=gen3:gen3 . /${appname}

# install the app
RUN poetry install --without dev --no-interaction

# Get version from tags if available
RUN echo "Latest tags (sorted by date):" && git tag --contains HEAD --sort=-taggerdate
RUN echo "Git describe tags:" && git describe --always --tags
RUN VERSION=$(git tag --contains HEAD --sort=-taggerdate | head -n 1) && if [ -z "$VERSION" ]; then \
        echo "Tag command failed or returned empty. Falling back to git describe."; \
            VERSION=$(git describe --always --tags); \
            echo "Using git describe VERSION: $VERSION"; \
    else \
        echo "Successfully found tag, VERSION: $VERSION"; \
    fi && git config --global --add safe.directory ${appname} && COMMIT=`git rev-parse HEAD` && echo "COMMIT=\"${COMMIT}\"" > ${appname}/version_data.py \
    && echo "VERSION=\"${VERSION}\"" >> ${appname}/version_data.py

# Final stage
FROM base

RUN  yum install -y postgresql-libs

COPY --from=builder /${appname} /${appname}

# Switch to non-root user 'gen3' for the serving process
USER gen3

WORKDIR /${appname}

CMD ["/bin/bash", "-c", "/${appname}/dockerrun.bash"]
