#!/bin/bash

docker run --rm \
    -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
    -v $1:/ros_ws:ro \
    -v $2:/output \
    ai-nodedoc:latest /ros_ws --output-dir /output --provider anthropic --model claude-sonnet-4-6
