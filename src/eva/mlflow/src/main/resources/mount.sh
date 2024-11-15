#!/bin/bash

set -o nounset
set -o errexit

ROOT_DIR=$(dirname $(readlink -f "$0"))

. "${ROOT_DIR}/../../../.env"
. "${ROOT_DIR}/../../../.env_prod"

MLFLOW_SHARE_SMB=$(basename $(dirname "${MLFLOW_SHARE_SERVER_DIR}"))-$(basename "${MLFLOW_SHARE_SERVER_DIR}")
if [ $(mount | grep "${MLFLOW_SHARE_SMB}" | wc -l) -eq 0 ]; then
  mkdir -p "${MLFLOW_SHARE_CLIENT_DIR}${MLFLOW_SHARE_SERVER_DIR}"
  diskutil unmount force "${MLFLOW_SHARE_CLIENT_DIR}${MLFLOW_SHARE_SERVER_DIR}" &>/dev/null || true
  mount_smbfs //GUEST:@"${MLFLOW_HOST_PROD}/${MLFLOW_SHARE_SMB}" "${MLFLOW_SHARE_CLIENT_DIR}${MLFLOW_SHARE_SERVER_DIR}"
fi

exit 0
