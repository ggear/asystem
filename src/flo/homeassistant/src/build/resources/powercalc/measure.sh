#!/bin/bash

docker run --rm --name=measure --env-file=.env -v $(pwd)/export:/app/export -v $(pwd)/.persistent:/app/.persistent -it bramgerritsen/powercalc-measure:latest
