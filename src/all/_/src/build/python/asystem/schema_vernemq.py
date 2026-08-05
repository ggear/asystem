import fnmatch
import json
import re
import textwrap

from asystem.schema import script

DIALECT = "vernemq"

ROLE_COLUMNS = {"state_topic": "state", "command_topic": "command", "availability_topic": "availability"}

TOPIC_COLUMNS = ("discovery_topic", "state_topic", "command_topic", "availability_topic")

DISCOVERY_COLUMNS = (
    "unique_id",
    "entity_namespace",
    "name",
    "state_class",
    "unit_of_measurement",
    "device_class",
    "icon",
    "force_update",
    "optimistic",
    "state_topic",
    "value_template",
    "command_topic",
    "availability_topic",
    "payload_on",
    "payload_off",
    "payload_available",
    "payload_not_available",
    "qos",
)

DISCOVERY_PAYLOAD = """
{
  "<home assistant mqtt discovery config, generated into src/main/resources/image/vernemq and published by vernemq.sh>"
}
"""

CONNECT = """
BROKER_ARGS=(-h "${VERNEMQ_SERVICE_PROD}" -p "${VERNEMQ_API_PORT}")

topics() {
  mosquitto_sub "${BROKER_ARGS[@]}" -F '%t' -t "$1" -W 5 2>/dev/null | grep -E "${2:-.}" | sort -u
}

payload() {
  mosquitto_sub "${BROKER_ARGS[@]}" -t "$1" -C 1 -W 2 2>/dev/null
}

declared() {
  find "${ROOT_DIR}/topics" -type f -print0 2>/dev/null |
    while IFS= read -r -d '' LEAF; do
      printf '%s\\n' "${LEAF#"${ROOT_DIR}"/topics/}"
    done | sort -u
}
"""


def leaf(topic, spec=None, document=None, role=""):
    if document is not None and role:
        payload = payload_for(document, role, topic)
    elif isinstance(spec, dict):
        payload = next((value for pattern, value in spec.items() if fnmatch.fnmatch(topic, pattern)), "")
    else:
        payload = spec or ""
    payload = "\n".join(line.rstrip() for line in textwrap.dedent(payload).splitlines()).strip()
    return payload + "\n" if payload else ""


def discovery(row):
    device_columns = [column for column in row.index
                      if column.startswith("device_") and column != "device_class"]
    discovery_dict = row[[column for column in DISCOVERY_COLUMNS if column in row.index]].dropna().to_dict()
    if "force_update" in discovery_dict:
        discovery_dict["force_update"] = _coerce_bool(discovery_dict["force_update"])
    if "qos" in discovery_dict:
        discovery_dict["qos"] = _coerce_int(discovery_dict["qos"])
    discovery_clone = {"default_entity_id": discovery_dict["entity_namespace"] + "." + discovery_dict["unique_id"]}
    del discovery_dict["entity_namespace"]
    discovery_clone.update(discovery_dict)
    discovery_dict = discovery_clone
    discovery_dict["device"] = row[device_columns].rename(
        {column: column.replace("device_", "") for column in device_columns}).dropna().to_dict()
    del discovery_dict["device"]["via_device"]
    if "connections" in discovery_dict["device"]:
        discovery_dict["device"]["connections"] = json.loads(discovery_dict["device"]["connections"])
    if "identifiers" in discovery_dict["device"]:
        discovery_dict["device"]["identifiers"] = _coerce_identifiers(discovery_dict["device"]["identifiers"])
    return json.dumps(discovery_dict, ensure_ascii=False, indent=2) + "\n"


def publish_script(module_name, topic_glob_discovery, topic_glob_data):
    topic_find_discovery = ("*/" + topic_glob_discovery.replace("+", "*").replace("#", "*") + "/*"
                            if topic_glob_discovery else "*")
    return """
#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

ROOT_DIR="$(dirname "$(readlink -f "$0")")/vernemq"

for f in "$ROOT_DIR/../../.env" "$ROOT_DIR/../../../../.env"; do [ -f "$f" ] && . "$f"; done

printf "\\nEntity Metadata publish script [{}] dropping discovery topics on [$VERNEMQ_SERVICE]:\\n"
mosquitto_sub -h $VERNEMQ_SERVICE -p $VERNEMQ_API_PORT -F '%t' -t "{}" -W 5 2>/dev/null | sort -u | \\
  while read topic; do
    echo "$topic"
    mosquitto_pub -h $VERNEMQ_SERVICE -p $VERNEMQ_API_PORT -t "$topic" -r -n
  done
mosquitto_sub -h $VERNEMQ_SERVICE -p $VERNEMQ_API_PORT --remove-retained -F '%t' -t "{}" -W 5 2>/dev/null

printf "\\nEntity Metadata publish script [{}] sleeping before dropping data topics ... " && sleep 2 && printf "done\\n\\n"

printf "Entity Metadata publish script [{}] dropping data topics on [$VERNEMQ_SERVICE]:\\n"
mosquitto_sub -h $VERNEMQ_SERVICE -p $VERNEMQ_API_PORT --remove-retained -F '%t' -t "{}" -W 1 2>/dev/null

printf "\\nEntity Metadata publish script [{}] sleeping before publishing discovery topics ... " && sleep 2 && printf "done\\n\\n"

printf "Entity Metadata publish script [{}] publishing discovery topics on [$VERNEMQ_SERVICE]:\\n"
find "$ROOT_DIR" -path "{}" -name "*.json" -print0 | sort -z | while read -d $'\\0' METADATA_FILE; do
  METADATA_TOPIC=$(dirname "${{METADATA_FILE/$ROOT_DIR\\//}}")
  mosquitto_pub -h $VERNEMQ_SERVICE -p $VERNEMQ_API_PORT -t "$METADATA_TOPIC" -f "$METADATA_FILE" -r
  printf "%s\\n" "$METADATA_TOPIC"
done
printf "\\n"
            """.format(
        module_name,
        topic_glob_discovery,
        topic_glob_discovery,
        module_name,
        module_name,
        topic_glob_data,
        module_name,
        module_name,
        topic_find_discovery,
    ).strip()


def describe_script(module_name, dialect, globs):
    return script(module_name, dialect, "describe", "print what the production broker actually retains", CONNECT, """
printf '\\nSchema describe [%s] against [%s]\\n\\n' "{}" "${{VERNEMQ_SERVICE_PROD}}"
{}
""".format(module_name, "\n".join(
        "printf '\\n== %s ==\\n' \"{0}\"\ntopics {1}".format(_expand(glob), _arguments(glob)) for glob in globs)))


def query_script(module_name, dialect):
    return script(module_name, dialect, "query", "print the retained payload of every declared topic", CONNECT, """
printf '\\nSchema query [%s] against [%s]\\n\\n' "{}" "${{VERNEMQ_SERVICE_PROD}}"
while IFS= read -r TOPIC; do
  printf '\\n== %s ==\\n' "${{TOPIC}}"
  payload "${{TOPIC}}"
done < <(declared)
""".format(module_name))


def verify_script(module_name, dialect, globs, commands):
    return script(module_name, dialect, "verify", "assert the broker retains exactly the declared topics", CONNECT, """
printf '\\nSchema verify [%s] against [%s]\\n\\n' "{}" "${{VERNEMQ_SERVICE_PROD}}"

COMMAND_TOPICS=({})

FAULTS=0

while IFS= read -r TOPIC; do
  for COMMAND_TOPIC in ${{COMMAND_TOPICS[@]+"${{COMMAND_TOPICS[@]}}"}}; do
    [ "${{TOPIC}}" == "${{COMMAND_TOPIC}}" ] && continue 2
  done
  RETAINED="$(payload "${{TOPIC}}")"
  if [ -z "${{RETAINED}}" ]; then
    FAULTS=$((FAULTS + 1))
    printf 'declared topic has no retained payload [%s]\\n' "${{TOPIC}}" >&2
  fi
done < <(declared)

RETAINED_FILE="$(mktemp)"
trap 'rm -f "${{RETAINED_FILE}}"' EXIT
{}
while IFS= read -r TOPIC; do
  [ -z "${{TOPIC}}" ] && continue
  if ! declared | grep -qxF "${{TOPIC}}"; then
    FAULTS=$((FAULTS + 1))
    printf 'retained topic is stale, nothing declares it [%s]\\n' "${{TOPIC}}" >&2
  fi
done < "${{RETAINED_FILE}}"

if [ "${{FAULTS}}" != "0" ]; then
  printf '\\nSchema verify [%s] found [%s] fault(s)\\n' "{}" "${{FAULTS}}" >&2
  exit 1
fi
printf '\\nSchema verify [%s] found no drift\\n' "{}"
""".format(module_name, " ".join('"{}"'.format(command) for command in commands), "\n".join(
        'topics {} >> "${{RETAINED_FILE}}"'.format(_arguments(glob)) for glob in globs),
           module_name, module_name))


def discover_script(module_name, dialect, globs):
    return script(module_name, dialect, "discover", "draft a declaration from what the broker retains", CONNECT, """
printf '\\nSchema discover [%s] against [%s], a drafting aid that is never an input to the build\\n\\n' "{}" "${{VERNEMQ_SERVICE_PROD}}"
{}
""".format(module_name, "\n".join(
        """while IFS= read -r TOPIC; do
  printf '\\n== %s ==\\n' "${{TOPIC}}"
  payload "${{TOPIC}}" | jq 'if type == "object" then map_values(type) else type end' 2>/dev/null || payload "${{TOPIC}}"
done < <(topics {})""".format(_arguments(glob)) for glob in globs)))


def render(member, indent=0):
    pad = "  " * indent
    if member.kind == "obj":
        lines = ["{"]
        for index, nested in enumerate(member.members):
            comma = "," if index < len(member.members) - 1 else ""
            lines.append('{}  "{}": {}{}'.format(pad, nested.key, render(nested, indent + 1), comma))
        lines.append(pad + "}")
        return "\n".join(lines)
    if member.enum:
        return "<{}>".format("|".join(member.enum))
    if member.kind == "bool":
        return "<true|false>"
    if member.kind in ("float", "int"):
        return "<number>"
    return '"<text>"' if indent else "<text>"


def payload_for(document, role, topic):
    payloads = [payload for payload in document.payloads if payload.role == role]
    for payload in payloads:
        if payload.match and fnmatch.fnmatch(topic, payload.match):
            return render(payload.root)
    for payload in payloads:
        if not payload.match:
            return render(payload.root)
    return ""


def _coerce_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "y", "1", "on"}:
            return True
        if normalized in {"false", "no", "n", "0", "off"}:
            return False
    return value


def _coerce_int(value):
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        normalized = value.strip()
        if normalized == "":
            return value
        try:
            return int(normalized)
        except ValueError:
            try:
                return int(float(normalized))
            except ValueError:
                return value
    return value


def _coerce_identifiers(value):
    if value is None:
        return value
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        normalized = value.strip()
        if normalized == "":
            return []
        if normalized.startswith("["):
            try:
                parsed = json.loads(normalized)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except ValueError:
                pass
        return [item.strip() for item in normalized.split(",") if item.strip()]
    return [str(value)]


def _arguments(glob):
    pattern = _pattern(glob)
    return '"{}"'.format(_expand(glob)) if not pattern else '"{}" "{}"'.format(_expand(glob), pattern)


def _expand(glob):
    return "/".join("+" if "${" in level else level for level in glob.split("/"))


def _pattern(glob):
    levels = glob.split("/")
    if all(re.fullmatch(r"\$\{[^}]+}", level) or "${" not in level for level in levels):
        return ""
    trailing = levels and levels[-1] == "#"
    parts = []
    for level in (levels[:-1] if trailing else levels):
        if level in ("+", "#"):
            parts.append("[^/]+" if level == "+" else "[^/]+(/[^/]+)*")
            continue
        parts.append("[^/]+".join(re.escape(chunk) for chunk in re.split(r"\$\{[^}]+}", level)))
    return "^" + "/".join(parts) + ("(/.*)?$" if trailing else "$")
