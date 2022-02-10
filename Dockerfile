FROM alpine:latest

COPY entrypoint.sh /entrypoint.sh
COPY update_data_volumes.py /update_data_volumes.py

RUN mkdir /docker
COPY Dockerfile.data /docker/Dockerfile.data

RUN apk add --update --no-cache docker python3 py3-pip bash

RUN pip3 install --upgrade pip python-dateutil requests bs4

ENTRYPOINT ["/entrypoint.sh"]
