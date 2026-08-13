import fnmatch
import json
import os
import re
import shutil
import textwrap
from os.path import abspath, exists, join

from asystem.schema.query import banner
from asystem.schema.runner import REPORT, script

DIALECT = "vernemq"
TARGET = "VERNEMQ_SERVICE_PROD"

PLACEHOLDER = r"\$\{[^}]+}"

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

CONNECT = REPORT + """
BROKER_ARGS=(-h "${TARGET_VARIABLE}" -p "${VERNEMQ_API_PORT}")

topics() {
  mosquitto_sub "${BROKER_ARGS[@]}" -F '%t' -t "$1" -W 5 2>/dev/null | grep -E "${2:-.}" | sort -u || true
}

payload() {
  mosquitto_sub "${BROKER_ARGS[@]}" -t "$1" -C 1 -W 2 2>/dev/null || true
}

declared() {
  find "${ROOT_DIR}/model" -type f -print0 2>/dev/null |
    while IFS= read -r -d '' LEAF; do
      printf '%s\\n' "${LEAF#"${ROOT_DIR}"/model/}"
    done | sort -u
}
""".replace("TARGET_VARIABLE", TARGET)


def artifacts(metadata_df, module_name, options):
    _validate_globs(metadata_df, module_name, options.topic_glob_discovery, options.topic_glob_data)
    topics = _topics(metadata_df, module_name)
    specs = _specs(module_name, options)
    if not topics:
        return {}
    document = options.document
    globs = [glob for glob in (options.topic_glob_discovery, options.topic_glob_data) if glob]
    generated = {}
    for column, column_topics in topics.items():
        role = ROLE_COLUMNS.get(column, "") if document is not None else ""
        for topic in column_topics:
            generated["model/{}".format(topic)] = (leaf(topic, specs.get(column, ""), document, role), False)
    generated["describe.sh"] = (describe_script(module_name, globs), True)
    generated["query.sh"] = (query_script(module_name), True)
    generated["verify.sh"] = (
        verify_script(module_name, globs, sorted(topics.get("command_topic", []))), True)
    return generated


def ship(metadata_df, module_name, module_root, schemas_dir, options):
    working_root = options.working_root
    working_dir = join(str(working_root), DIALECT)
    if exists(working_dir):
        shutil.rmtree(working_dir)
    for _, row in metadata_df.iterrows():
        discovery_dir = abspath(join(working_dir, str(row["discovery_topic"])))
        os.makedirs(discovery_dir)
        discovery_path = abspath(join(discovery_dir, str(row["unique_id"]) + ".json"))
        with open(discovery_path, 'w') as discovery_file:
            discovery_file.write(discovery(row))
        print("Build generate script [{}] entity metadata [sensor.{}] persisted to [{}]"
              .format(module_name, row["unique_id"], discovery_path))
    publish_path = abspath(join(str(working_root), DIALECT + ".sh"))
    with open(publish_path, 'w') as publish_file:
        publish_file.write(publish_script(module_name, options.topic_glob_discovery, options.topic_glob_data))
    os.chmod(publish_path, 0o750)
    print("Build generate script [{}] entity metadata publish script persisted to [{}]"
          .format(module_name, publish_path))


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
    device_columns = [column for column in row.index if column.startswith("device_") and column != "device_class"]
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
    discovery_dict["device"].pop("via_device", None)
    if "connections" in discovery_dict["device"]:
        discovery_dict["device"]["connections"] = json.loads(discovery_dict["device"]["connections"])
    if "identifiers" in discovery_dict["device"]:
        discovery_dict["device"]["identifiers"] = _coerce_identifiers(discovery_dict["device"]["identifiers"])
    return json.dumps(discovery_dict, ensure_ascii=False, indent=2) + "\n"


def publish_script(module_name, topic_glob_discovery, topic_glob_data):
    topic_find_discovery = ("*/" + topic_glob_discovery.replace("+", "*").replace("#", "*") + "/*" if topic_glob_discovery else "*")
    return """
#!/usr/bin/env bash
{}

ROOT_DIR="$(dirname "$(readlink -f "$0")")/vernemq"

ENV_DIR="$ROOT_DIR"
while [ "$ENV_DIR" != "/" ] && [ ! -f "$ENV_DIR/.env" ]; do ENV_DIR="$(dirname "$ENV_DIR")"; done
# shellcheck disable=SC1091
[ -f "$ENV_DIR/.env" ] && . "$ENV_DIR/.env"

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
        banner(),
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


def describe_script(module_name, globs):
    return script(module_name, DIALECT, "describe", "print what the production broker actually retains", CONNECT, """
printf '\\nSchema describe [%s] against [%s]\\n\\n' "{}" "${{{}}}"
{}
""".format(module_name, TARGET, "\n".join(
        "printf '\\n== %s ==\\n' \"{}\"\ntopics {}".format(_expand(glob), _arguments(glob)) for glob in globs)))


def query_script(module_name):
    return script(module_name, DIALECT, "query", "print the retained payload of every declared topic", CONNECT, """
printf '\\nSchema query [%s] against [%s]\\n\\n' "{}" "${{{}}}"
while IFS= read -r TOPIC; do
  printf '\\n== %s ==\\n' "${{TOPIC}}"
  payload "${{TOPIC}}"
done < <(declared)
""".format(module_name, TARGET))


def verify_script(module_name, globs, commands):
    return script(module_name, DIALECT, "verify", "assert the broker retains exactly the declared topics", CONNECT, """
printf '\\nSchema verify [%s] against [%s]\\n\\n' "{}" "${{{}}}"

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
""".format(module_name, TARGET, " ".join('"{}"'.format(command) for command in commands), "\n".join(
        'topics {} >> "${{RETAINED_FILE}}"'.format(_arguments(glob)) for glob in globs), module_name, module_name))


def render(member, indent=0):
    pad = "  " * indent
    if member.members:
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
                numeric = float(normalized)
                return int(numeric) if numeric.is_integer() else value
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


def _validate_globs(metadata_df, module_name, topic_glob_discovery, topic_glob_data):
    for topic_glob, topic_glob_name, topic_glob_column in (
            (topic_glob_discovery, "topic_glob_discovery", "discovery_topic"),
            (topic_glob_data, "topic_glob_data", "state_topic")):
        if topic_glob is None:
            continue
        unmatched = [topic for topic in _column_topics(metadata_df, topic_glob_column)
                     if not _glob_match(topic_glob, topic)]
        if unmatched:
            raise ValueError(
                "Build generate script [{}] {} [{}] does not match entity_metadata.xlsx {} topic(s) {}: "
                "update the glob or the spreadsheet so they agree"
                .format(module_name, topic_glob_name, topic_glob, topic_glob_column, unmatched))


def _glob_match(topic_glob, topic):
    glob_levels = topic_glob.split("/")
    topic_levels = topic.split("/")
    for index, glob_level in enumerate(glob_levels):
        if glob_level == "#":
            return True
        if index >= len(topic_levels):
            return False
        if glob_level == "+":
            continue
        if not fnmatch.fnmatchcase(topic_levels[index], re.sub(PLACEHOLDER, "*", glob_level)):
            return False
    return len(glob_levels) == len(topic_levels)


def _column_topics(metadata_df, column):
    if column not in metadata_df.columns:
        return []
    return sorted({topic.strip() for topic in metadata_df[column].dropna().unique() if topic.strip()})


def _topics(metadata_df, module_name):
    topics = {column: _column_topics(metadata_df, column) for column in TOPIC_COLUMNS}
    topics = {column: column_topics for column, column_topics in topics.items() if column_topics}
    topics_all = sorted({topic for column_topics in topics.values() for topic in column_topics})
    for topic in topics_all:
        for topic_other in topics_all:
            if topic_other != topic and topic_other.startswith(topic + "/"):
                raise ValueError(
                    "Build generate script [{}] entity schema topic [{}] is a path prefix of [{}]: "
                    "cannot write a payload leaf file and a directory at the same path"
                    .format(module_name, topic, topic_other))
    return topics


def _specs(module_name, options):
    document = options.document
    specs = {column: spec for column, spec in (("state_topic", options.state),
                                               ("command_topic", options.command),
                                               ("availability_topic", options.availability))
             if spec is not None}
    if document is not None:
        for column, role in ROLE_COLUMNS.items():
            if column in specs and any(payload.role == role for payload in document.payloads):
                raise ValueError(
                    "Build generate script [{}] role [{}] is declared in code and also passed as a literal [{}]: "
                    "supply one or the other, never both".format(module_name, role, column))
    specs["discovery_topic"] = DISCOVERY_PAYLOAD
    return specs


def _arguments(glob):
    pattern = _pattern(glob)
    return '"{}"'.format(_expand(glob)) if not pattern else '"{}" "{}"'.format(_expand(glob), pattern)


def _expand(glob):
    return "/".join("+" if "${" in level else level for level in glob.split("/"))


def _pattern(glob):
    levels = glob.split("/")
    if all(re.fullmatch(PLACEHOLDER, level) or "${" not in level for level in levels):
        return ""
    trailing = levels and levels[-1] == "#"
    parts = []
    for level in (levels[:-1] if trailing else levels):
        if level in ("+", "#"):
            parts.append("[^/]+" if level == "+" else "[^/]+(/[^/]+)*")
            continue
        parts.append("[^/]+".join(re.escape(chunk) for chunk in re.split(PLACEHOLDER, level)))
    return "^" + "/".join(parts) + ("(/.*)?$" if trailing else "$")
