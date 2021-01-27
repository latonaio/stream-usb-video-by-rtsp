#!/bin/sh

NUM=${1:-1}
PUSH=$2
DATE="$(date "+%Y%m%d%H%M")"
REPOSITORY_PREFIX="latonaio"
SERVICE_NAME="stream-usb-video-by-rtsp"

DOCKER_BUILDKIT=1 docker build --progress=plain -t ${SERVICE_NAME}:"${DATE}" .

# tagging
for n in `seq 1 $NUM`
do
  docker tag ${SERVICE_NAME}:"${DATE}" ${SERVICE_NAME}-${n}:latest
  docker tag ${SERVICE_NAME}:"${DATE}" ${REPOSITORY_PREFIX}/${SERVICE_NAME}-${n}:"${DATE}"
  docker tag ${REPOSITORY_PREFIX}/${SERVICE_NAME}-${n}:"${DATE}" ${REPOSITORY_PREFIX}/${SERVICE_NAME}-${n}:latest
done

if [[ $PUSH == "push" ]]; then
    docker push ${REPOSITORY_PREFIX}/${SERVICE_NAME}:"${DATE}"
    docker push ${REPOSITORY_PREFIX}/${SERVICE_NAME}:latest
fi
