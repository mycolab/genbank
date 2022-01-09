#!/usr/bin/env bash

[[ -z $PROJECT ]] && PROJECT=mycolab
export PROJECT

./docker-net.sh || exit 1
docker-compose -p $PROJECT up -d
