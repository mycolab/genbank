#!/usr/bin/env bash

[[ -z $PROJECT ]] && PROJECT=mycolab
export PROJECT

docker compose -p $PROJECT down
