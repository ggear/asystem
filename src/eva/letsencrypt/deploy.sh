#!/bin/sh

ROOT_DIR=$(dirname $(readlink -f "$0"))

for CERTS_SCRIPT in $(find "${ROOT_DIR}/../.." -name certs.sh -type f -path "*/src/*" ! -path "*/target/*" | sed 's/\/src\/main\// /' | cut -d ' ' -f1); do
  DEPLOY_SCRIPT="${CERTS_SCRIPT}/deploy.sh"
  if [ -f "${DEPLOY_SCRIPT}" ]; then
    echo "" &&
      echo "----------------------------------------------------------------------------------------------------" &&
      echo "Executing deploy script [$(realpath ${DEPLOY_SCRIPT})]" &&
      echo "----------------------------------------------------------------------------------------------------" &&
      echo "" && ${DEPLOY_SCRIPT}
  fi
done
