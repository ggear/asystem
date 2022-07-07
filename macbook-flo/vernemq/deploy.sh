#!/bin/sh

export $(xargs <.env)

export VERNEMQ_HOST=${VERNEMQ_HOST_PROD}

./src/main/resources/config/publish.sh
