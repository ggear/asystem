#!/bin/bash

SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/latest

# shellcheck disable=SC1091
. "${SERVICE_INSTALL}/.env"

chmod +x "${SERVICE_INSTALL}/supervisor"
rm -f /usr/local/bin/atop
cat >/usr/local/bin/atop <<EOF
#!/bin/bash

${SERVICE_INSTALL}/supervisor watch -m local -F 1 "\$@"

EOF
chmod +x /usr/local/bin/atop
rm -f /usr/local/bin/atops
cat >/usr/local/bin/atops <<EOF
#!/bin/bash

${SERVICE_INSTALL}/supervisor watch -m remote "\$@"

EOF
chmod +x /usr/local/bin/atops
if [[ "${SERVICE_FORM_FACTOR:-}" == "edge" || "${SERVICE_FORM_FACTOR:-}" == "server" ]]; then
  rm -f /usr/local/bin/abackup
  cat >/usr/local/bin/abackup <<EOF
#!/bin/bash

set -a
[ -f "${SERVICE_INSTALL}/.env" ] && . "${SERVICE_INSTALL}/.env"
set +a
${SERVICE_INSTALL}/supervisor backup "\$@"

EOF
  chmod +x /usr/local/bin/abackup
fi
chmod +x "${SERVICE_INSTALL}/image/backups.sh"
rm -f /usr/local/bin/abackups
cat >/usr/local/bin/abackups <<EOF
#!/bin/bash

${SERVICE_INSTALL}/image/backups.sh "\$@"

EOF
chmod +x /usr/local/bin/abackups
if [ -d /etc/bash_completion.d ]; then
  completion="$(mktemp)"
  {
    "${SERVICE_INSTALL}/supervisor" completion bash &&
      cat <<EOF

__supervisor_alias() {
  local typed="\${COMP_WORDS[0]}" bin="${SERVICE_INSTALL}/supervisor" verb="\$1"
  local words=("\${bin}" "\${verb}" "\${COMP_WORDS[@]:1}")
  local line="\${bin} \${verb}\${COMP_LINE#"\${typed}"}"
  local point=\$((COMP_POINT + \${#line} - \${#COMP_LINE}))
  local COMP_WORDS=("\${words[@]}") COMP_CWORD=\$((COMP_CWORD + 1)) COMP_LINE="\${line}" COMP_POINT="\${point}"
  __start_supervisor
}
_abackup() { __supervisor_alias backup; }
_atop() { __supervisor_alias watch; }
complete -o default -F _abackup abackup
complete -o default -F _atop atop atops

_abackups() {
  local cur="\${COMP_WORDS[COMP_CWORD]}"
  if [ "\${COMP_CWORD}" -eq 1 ]; then
    mapfile -t COMPREPLY < <(compgen -W "start stop tail list clean help" -- "\${cur}")
  elif [ "\${COMP_WORDS[1]}" = "start" ]; then
    mapfile -t COMPREPLY < <(compgen -W "--scrub" -- "\${cur}")
  fi
}
complete -F _abackups abackups
EOF
  } >"${completion}" && install -m 644 "${completion}" /etc/bash_completion.d/supervisor
  rm -f "${completion}"
fi
