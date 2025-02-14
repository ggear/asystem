#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

echo ""
for MODULE_DIR in $(find "${ROOT_DIR}/../.." -name certificates.sh -type f -path "*/src/*" ! -path "*/target/*" | sed 's/\/src\/main\// /' | cut -d ' ' -f1); do
  echo "----------------------------------------------------------------------------------------------------" &&
    echo "Executing deploy script for module [$(basename ${MODULE_DIR})] starting ..." &&
    echo "----------------------------------------------------------------------------------------------------" &&
    echo ""
  [ -f "${MODULE_DIR}/generate.sh" ] && "${MODULE_DIR}/generate.sh"
  [ -f "${MODULE_DIR}/deploy.sh" ] && "${MODULE_DIR}/deploy.sh"
  echo "" && echo "----------------------------------------------------------------------------------------------------" &&
    echo "Executing deploy script for module [$(basename ${MODULE_DIR})] finished" &&
    echo "----------------------------------------------------------------------------------------------------" &&
    echo ""
done
