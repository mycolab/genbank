#!/bin/bash
if [ -f venv/bin/activate ]; then
  source venv/bin/activate
fi

if [[ $(docker network ls -q -f name=${PROJECT}) ]]; then
  docker network rm ${PROJECT}
fi
