#!/bin/bash

docker run --rm \
    -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
    -e OPENAI_API_KEY=$OPENAI_API_KEY \
    -e OPENROUTER_API_KEY=$OPENROUTER_API_KEY \
    -v $1:/ros_ws:ro \
    -v $2:/output \
    ai-nodedoc:latest /ros_ws --output-dir /output "${@:3}"
