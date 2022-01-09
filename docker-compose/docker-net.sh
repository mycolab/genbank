#!/bin/bash

[[ -z $PROJECT ]] && PROJECT=mycolab
export PROJECT

if [[ ! $(docker network ls -q -f name="${PROJECT}") ]]; then
  docker network create "${PROJECT}" 2> /dev/null
fi
