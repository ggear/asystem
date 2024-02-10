#!/bin/bash

. ../../../generate.sh

VERSION=main
pull_repo $(pwd) grafana grafonnet grafana/grafonnet ${VERSION} ${1}

VERSION=v0.2.1
pull_repo $(pwd) grafana grizzly grafana/grizzly ${VERSION} ${1}
