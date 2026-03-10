#!/bin/bash

set -x
SCRIPT_DIR=`dirname $( readlink -m $( type -p $0 ))`

docker build -f $SCRIPT_DIR/Dockerfile -t ai-nodedoc:latest $SCRIPT_DIR/.. \
  --build-arg USERNAME=$(whoami) \
  --build-arg UID=$(id -u) --build-arg GID=$(id -g)
