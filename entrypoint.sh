#! /bin/bash

# if INPUT_DOCKER_NAME is set, then run docker login
if [ -z ${INPUT_DOCKER_NAME+x} ]; then
  echo "Docker credentials not available. Skipping data volume update..."
  exit 0
fi

echo "Logging into Docker ..."
echo "$INPUT_DOCKER_PASS" | docker login -u "$INPUT_DOCKER_NAME" --password-stdin

python3 /update_data_volumes.py
