#!/bin/bash
# REPOSITORY가 <none>인 모든 도커 이미지 삭제
# docker images | grep '<none>' | awk '{print $3}' | xargs -r docker rmi
docker image prune