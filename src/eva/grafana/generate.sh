#!/bin/bash

. ../../../.env_fab
. ../../../generate.sh

ROOT_DIR=$(dirname $(readlink -f "$0"))

VERSION=${GRIZZLY_VERSION}
pull_repo $(pwd) grafana grizzly grafana/grizzly ${VERSION} ${1}

VERSION=ggear-grafonnet
pull_repo $(pwd) grafana grafonnet-lib ggear/grafonnet-lib ${VERSION} ${1}
rm -rf ${ROOT_DIR}/src/main/resources/image/libraries/grafonnet-lib
mkdir -p ${ROOT_DIR}/src/main/resources/image/libraries/grafonnet-lib
cp -rvf ${ROOT_DIR}/../../../.deps/grafana/grafonnet-lib/grafonnet ${ROOT_DIR}/src/main/resources/image/libraries/grafonnet-lib
