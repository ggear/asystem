#!/bin/bash

SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/latest

chmod +x "${SERVICE_INSTALL}/storage"
rm -f /usr/local/bin/aspace
cat >/usr/local/bin/aspace <<EOF
#!/bin/bash

${SERVICE_INSTALL}/storage space "\$@"

EOF
chmod +x /usr/local/bin/aspace
rm -f /usr/local/bin/amount
cat >/usr/local/bin/amount <<EOF
#!/bin/bash

${SERVICE_INSTALL}/storage mount "\$@"

EOF
chmod +x /usr/local/bin/amount
if [ -d /etc/bash_completion.d ]; then
  completion="$(mktemp)"
  {
    "${SERVICE_INSTALL}/storage" completion bash &&
      cat <<EOF

__storage_alias() {
  local typed="\${COMP_WORDS[0]}" bin="${SERVICE_INSTALL}/storage" verb="\$1"
  local words=("\${bin}" "\${verb}" "\${COMP_WORDS[@]:1}")
  local line="\${bin} \${verb}\${COMP_LINE#"\${typed}"}"
  local point=\$((COMP_POINT + \${#line} - \${#COMP_LINE}))
  local COMP_WORDS=("\${words[@]}") COMP_CWORD=\$((COMP_CWORD + 1)) COMP_LINE="\${line}" COMP_POINT="\${point}"
  __start_storage
}
_aspace() { __storage_alias space; }
_amount() { __storage_alias mount; }
complete -o default -F _aspace aspace
complete -o default -F _amount amount
EOF
  } >"${completion}" && install -m 644 "${completion}" /etc/bash_completion.d/storage
  rm -f "${completion}"
fi
