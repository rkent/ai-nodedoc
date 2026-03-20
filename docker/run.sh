#!/bin/bash

mkdir -p $2

docker run --rm \
    -v $1:/ros_ws:ro \
    -v $2:/output \
    -v /srv:/srv \
    -v $(pwd):/app \
    ai-nodedoc:latest /ros_ws --output-dir /output "${@:3}"
