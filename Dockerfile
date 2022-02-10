FROM dtcenter/metplus-envs:metplus-action-data-update

COPY entrypoint.sh /entrypoint.sh
COPY update_data_volumes.py /update_data_volumes.py

RUN mkdir /docker
COPY Dockerfile.data /docker/Dockerfile.data

ENTRYPOINT ["/entrypoint.sh"]
