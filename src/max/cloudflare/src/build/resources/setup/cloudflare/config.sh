#!/usr/bin/env bash
################################################################################
# Operator script, reconciles the Cloudflare account state that the screenshots
# in this directory document, against the resources declared in the module env
# variable [CLOUDFLARE_RESOURCES], reporting drift and optionally applying it.
#
# Not run by any build, test or deploy task, see the module CLAUDE.md.
################################################################################

set -uo pipefail

CONFIG_VERBOSE=${CONFIG_VERBOSE:-false}
CONFIG_APPLY=${CONFIG_APPLY:-false}
while [[ $# -gt 0 ]]; do
  case $1 in
  -v | --verbose)
    CONFIG_VERBOSE=true
    shift
    ;;
  -a | --apply)
    CONFIG_APPLY=true
    shift
    ;;
  -h | --help | -*)
    echo "Usage: ${0} [-a|--apply] [-v|--verbose] [-h|--help]"
    echo "       cloudflare config verify the account carries the declared dns, access app and policy"
    exit 2
    ;;
  *)
    shift
    ;;
  esac
done

ROOT_DIR="$(dirname "$(readlink -f "$0")")"
MODULE_DIR="${ROOT_DIR}"
while [ "${MODULE_DIR}" != "/" ] && [ ! -f "${MODULE_DIR}/.env" ]; do
  MODULE_DIR="$(dirname "${MODULE_DIR}")"
done

if [ ! -f "${MODULE_DIR}/.env" ]; then
  echo "Config script [cloudflare] could not find env file [.env] searching up from [${ROOT_DIR}]" >&2
  exit 1
fi
set -a
# shellcheck disable=SC1091
. "${MODULE_DIR}/.env"
set +a

if [ "${CONFIG_VERBOSE}" == true ]; then
  set -x
fi

DOMAIN="janeandgraham.com"
DOMAIN_API="data"
POLICY_NAME="sheets-service-token"
SESSION_DURATION="24h"

API_URL="https://api.cloudflare.com/client/v4"
API_TOKEN="${CLOUDFLARE_API_TOKEN:-}"
ACCOUNT_ID="${CLOUDFLARE_ACCOUNT_ID:-}"
ZONE_ID="${CLOUDFLARE_ZONE_ID:-}"
TUNNEL_ID="${CLOUDFLARE_ID:-}"
RESOURCES="${CLOUDFLARE_RESOURCES:-}"

for VARIABLE in API_TOKEN ACCOUNT_ID TUNNEL_ID RESOURCES; do
  if [ -z "${!VARIABLE}" ]; then
    echo "Config script [cloudflare] could not resolve [${VARIABLE}] from it or any fallback, declare it in the module env files" >&2
    exit 1
  fi
done

FAULTS=0

log() {
  local LABEL="$1"
  local VALUE="$2"
  local FILL
  FILL="$(printf '%*s' $((72 - ${#LABEL})) '' | tr ' ' '.')"
  printf '%s%s [%s]\n' "${LABEL}" "${FILL}" "${VALUE}"
}

fault() {
  FAULTS=$((FAULTS + 1))
  log "$1" "$2"
}

api() {
  local METHOD="$1"
  local PATH_URL="$2"
  local BODY="${3:-}"
  local RESPONSE
  if [ -z "${BODY}" ]; then
    RESPONSE="$(curl -sf -X "${METHOD}" "${API_URL}${PATH_URL}" \
      -H "Authorization: Bearer ${API_TOKEN}")"
  else
    RESPONSE="$(curl -sf -X "${METHOD}" "${API_URL}${PATH_URL}" \
      -H "Authorization: Bearer ${API_TOKEN}" \
      -H "Content-Type: application/json" \
      --data "${BODY}")"
  fi
  if [ -z "${RESPONSE}" ]; then
    echo "Config script [cloudflare] got no response calling [${METHOD}] [${PATH_URL}]" >&2
    return 1
  fi
  if [ "$(jq -r '.success' <<<"${RESPONSE}")" != "true" ]; then
    echo "Config script [cloudflare] failed calling [${METHOD}] [${PATH_URL}] with error [$(jq -c '.errors' <<<"${RESPONSE}")]" >&2
    return 1
  fi
  jq -c '.result' <<<"${RESPONSE}"
}

if [ -z "${ZONE_ID}" ]; then
  ZONE_ID="$(api GET "/zones?name=${DOMAIN}" | jq -r '.[0].id // empty')"
  if [ -z "${ZONE_ID}" ]; then
    echo "Config script [cloudflare] could not resolve a zone for domain [${DOMAIN}]" >&2
    exit 1
  fi
fi

printf '\nConfig verify [%s] against account [%s] tunnel [%s]\n\n' "cloudflare" "${ACCOUNT_ID}" "${TUNNEL_ID}"

reconcile_record() {
  local RESOURCE="$1"
  local HOSTNAME="${RESOURCE}.${DOMAIN}"
  local CONTENT="${TUNNEL_ID}.cfargotunnel.com"
  local RECORD RECORD_ID
  RECORD="$(api GET "/zones/${ZONE_ID}/dns_records?type=CNAME&name=${HOSTNAME}")" || return 1
  RECORD_ID="$(jq -r '.[0].id // empty' <<<"${RECORD}")"
  if [ -n "${RECORD_ID}" ] &&
    [ "$(jq -r '.[0].content' <<<"${RECORD}")" == "${CONTENT}" ] &&
    [ "$(jq -r '.[0].proxied' <<<"${RECORD}")" == "true" ]; then
    log "dns record [${HOSTNAME}]" "ok"
    return 0
  fi
  if [ "${CONFIG_APPLY}" != true ]; then
    fault "dns record [${HOSTNAME}]" "$([ -n "${RECORD_ID}" ] && echo "wrong target or unproxied" || echo "missing")"
    return 0
  fi
  local BODY
  BODY="$(jq -nc --arg name "${HOSTNAME}" --arg content "${CONTENT}" \
    '{type: "CNAME", name: $name, content: $content, proxied: true, ttl: 1}')"
  if [ -n "${RECORD_ID}" ]; then
    api PATCH "/zones/${ZONE_ID}/dns_records/${RECORD_ID}" "${BODY}" >/dev/null || return 1
    log "dns record [${HOSTNAME}]" "updated"
  else
    api POST "/zones/${ZONE_ID}/dns_records" "${BODY}" >/dev/null || return 1
    log "dns record [${HOSTNAME}]" "created"
  fi
}

reconcile_token() {
  local RESOURCE="$1"
  local NAME="sheets-${RESOURCE}"
  local TOKENS CREATED
  TOKENS="$(api GET "/accounts/${ACCOUNT_ID}/access/service_tokens")" || return 1
  TOKEN_ID="$(jq -r --arg name "${NAME}" '.[] | select(.name == $name) | .id' <<<"${TOKENS}" | head -1)"
  if [ -n "${TOKEN_ID}" ]; then
    log "service token [${NAME}]" "ok"
    return 0
  fi
  if [ "${CONFIG_APPLY}" != true ]; then
    fault "service token [${NAME}]" "missing"
    return 0
  fi
  CREATED="$(api POST "/accounts/${ACCOUNT_ID}/access/service_tokens" \
    "$(jq -nc --arg name "${NAME}" '{name: $name}')")" || return 1
  TOKEN_ID="$(jq -r '.id' <<<"${CREATED}")"
  log "service token [${NAME}]" "created"
  printf '\n'
  log "  client id" "$(jq -r '.client_id' <<<"${CREATED}")"
  log "  client secret" "$(jq -r '.client_secret' <<<"${CREATED}")"
  printf '\n  The secret above is shown once only, store it in the caller now\n\n'
}

reconcile_policy() {
  local POLICIES CREATED
  POLICIES="$(api GET "/accounts/${ACCOUNT_ID}/access/policies")" || return 1
  POLICY_ID="$(jq -r --arg name "${POLICY_NAME}" '.[] | select(.name == $name) | .id' <<<"${POLICIES}" | head -1)"
  if [ -n "${POLICY_ID}" ]; then
    if jq -e --arg id "${TOKEN_ID}" --arg name "${POLICY_NAME}" \
      '.[] | select(.name == $name) | select(.decision == "non_identity")
       | select([.include[]? | select(.service_token.token_id == $id)] | length > 0)' \
      <<<"${POLICIES}" >/dev/null; then
      log "access policy [${POLICY_NAME}]" "ok"
    else
      fault "access policy [${POLICY_NAME}]" "does not admit the service token"
    fi
    return 0
  fi
  if [ "${CONFIG_APPLY}" != true ]; then
    fault "access policy [${POLICY_NAME}]" "missing"
    return 0
  fi
  CREATED="$(api POST "/accounts/${ACCOUNT_ID}/access/policies" \
    "$(jq -nc --arg name "${POLICY_NAME}" --arg id "${TOKEN_ID}" \
      '{name: $name, decision: "non_identity", include: [{service_token: {token_id: $id}}]}')")" || return 1
  POLICY_ID="$(jq -r '.id' <<<"${CREATED}")"
  log "access policy [${POLICY_NAME}]" "created"
}

reconcile_application() {
  local RESOURCE="$1"
  local HOSTNAME="${RESOURCE}.${DOMAIN}"
  local ORIGIN="${RESOURCE}.${DOMAIN_API}.${DOMAIN}"
  local APPS APP_ID BODY
  APPS="$(api GET "/accounts/${ACCOUNT_ID}/access/apps")" || return 1
  APP_ID="$(jq -r --arg domain "${HOSTNAME}" '.[] | select(.domain == $domain) | .id' <<<"${APPS}" | head -1)"
  BODY="$(jq -nc --arg name "${RESOURCE}" --arg domain "${HOSTNAME}" \
    --arg session "${SESSION_DURATION}" --arg policy "${POLICY_ID}" \
    '{name: $name, type: "self_hosted", domain: $domain, session_duration: $session,
      policies: [{id: $policy, precedence: 1}]}')"
  if [ -z "${APP_ID}" ]; then
    if [ "${CONFIG_APPLY}" != true ]; then
      fault "access application [${HOSTNAME}]" "missing"
      return 0
    fi
    api POST "/accounts/${ACCOUNT_ID}/access/apps" "${BODY}" >/dev/null || return 1
    log "access application [${HOSTNAME}]" "created"
    return 0
  fi
  local BOUND
  BOUND="$(api GET "/accounts/${ACCOUNT_ID}/access/apps/${APP_ID}/policies")" || return 1
  if jq -e --arg id "${POLICY_ID}" '[.[]? | select(.id == $id)] | length > 0' <<<"${BOUND}" >/dev/null; then
    log "access application [${HOSTNAME}]" "ok"
    return 0
  fi
  if [ "${CONFIG_APPLY}" != true ]; then
    fault "access application [${HOSTNAME}]" "not bound to policy [${POLICY_NAME}]"
    return 0
  fi
  api PUT "/accounts/${ACCOUNT_ID}/access/apps/${APP_ID}" "${BODY}" >/dev/null || return 1
  log "access application [${HOSTNAME}]" "updated"
  log "  origin served by nginx" "${ORIGIN}"
}

for RESOURCE in ${RESOURCES//,/ }; do
  RESOURCE="$(tr '[:upper:]' '[:lower:]' <<<"${RESOURCE//[[:space:]]/}")"
  [ -z "${RESOURCE}" ] && continue
  printf -- '-- resource [%s]\n\n' "${RESOURCE}"
  TOKEN_ID=""
  POLICY_ID=""
  reconcile_record "${RESOURCE}" || exit 1
  reconcile_token "${RESOURCE}" || exit 1
  if [ -z "${TOKEN_ID}" ]; then
    fault "access policy [${POLICY_NAME}]" "skipped, no service token"
    fault "access application [${RESOURCE}.${DOMAIN}]" "skipped, no service token"
    printf '\n'
    continue
  fi
  reconcile_policy || exit 1
  if [ -z "${POLICY_ID}" ]; then
    fault "access application [${RESOURCE}.${DOMAIN}]" "skipped, no access policy"
    printf '\n'
    continue
  fi
  reconcile_application "${RESOURCE}" || exit 1
  printf '\n'
done

if [ "${FAULTS}" != "0" ]; then
  printf '\nConfig verify [%s] found [%s] fault(s), rerun with [--apply] to reconcile\n' "cloudflare" "${FAULTS}" >&2
  exit 1
fi
printf '\nConfig verify [%s] found no drift\n' "cloudflare"
