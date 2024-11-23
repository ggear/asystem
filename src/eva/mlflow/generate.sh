#!/bin/bash

. ../../../.env_fab
. ../../../generate.sh

ROOT_DIR=$(dirname $(readlink -f "$0"))

pull_repo $(pwd) mlflow mlflow mlflow/mlflow v${MLFLOW_VERSION} ${1}
