import fnmatch
import json
import os
import re
import shutil
import subprocess
import textwrap
from os.path import abspath, basename, exists, join

from asystem.bootstrap import load_bootstrap_env_value, load_bootstrap_root
from asystem.schema.document import (
    SchemaBrokerMember,
    SchemaBrokerPayload,
    SchemaDocument,
    SchemaUnreachable,
)
from asystem.schema.query import banner
from asystem.schema.runner import REPORT, instance_runner, resolved, script, table

DIALECT = "vernemq"
SHIPPED = "broker"
TARGET = "VERNEMQ_SERVICE_PROD"

ENV = ".env"
TIMEOUT = 15
DISCOVERED = "discovered"
LEAF = "payload"
WINDOW = 2
AWAIT = 1

PLACEHOLDER = r"\$\{[^}]+}"

BINDING = re.compile(r"\$([A-Z][A-Z0-9_]*)")

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

CONNECT = REPORT + table(clip=0) + """
BROKER_ARGS=(-h "${BROKER_SERVICE}" -p "${BROKER_PORT}")
SCHEMA_WINDOW="${SCHEMA_WINDOW:-SCHEMA_WINDOW_DEFAULT}"
SCHEMA_AWAIT="${SCHEMA_AWAIT:-SCHEMA_AWAIT_DEFAULT}"

topics() {
  mosquitto_sub "${BROKER_ARGS[@]}" -F '%r %t' -t "$1" -W "${SCHEMA_WINDOW}" 2>/dev/null | sed -n 's/^1 //p' | grep -E "${2:-.}" | sort -u || true
}

payload() {
  mosquitto_sub "${BROKER_ARGS[@]}" -F '%r\\n%p' -t "$1" -C 1 -W "${SCHEMA_AWAIT}" 2>/dev/null | awk 'NR==1{if($0!="1") exit} NR>1' || true
}

declared() {
  find "${ROOT_DIR}/model" -type f -name 'SCHEMA_LEAF' -print0 2>/dev/null |
    while IFS= read -r -d '' LEAF; do
      TOPIC="${LEAF#"${ROOT_DIR}"/model/}"
      printf '%s\\n' "${TOPIC%/SCHEMA_LEAF}"
    done | sort -u
}

listed() {
  jq -R '{topic: .}' | table
}

faulted() {
  jq -nc --arg topic "$1" --arg fault "$2" '{topic: $topic, fault: $fault}'
}
""".replace("SCHEMA_LEAF", LEAF).replace(
    "SCHEMA_WINDOW_DEFAULT", str(WINDOW)).replace("SCHEMA_AWAIT_DEFAULT", str(AWAIT))


AWAITED = 300

CONFIG = REPORT + """
BROKER_ARGS=(-h "${BROKER_SERVICE}" -p "${BROKER_PORT}")

AWAITED_TIMEOUT=${AWAITED_TIMEOUT:-SCHEMA_AWAITED}

awaited() {
  local started=${SECONDS} payload
  while true; do
    payload="$(mosquitto_sub "${BROKER_ARGS[@]}" -t "$1" -W 1 2>/dev/null)"
    if [ -n "${payload}" ] && jq -re "$2" <<<"${payload}" >/dev/null 2>&1; then
      return 0
    fi
    if [ $((SECONDS - started)) -ge "${AWAITED_TIMEOUT}" ]; then
      fail "Waited [$((SECONDS - started))] seconds for [$3] on topic [$1] against broker [${BROKER_SERVICE}]" \
        "The topic held no payload matching [$2], check the service is publishing and the broker is reachable"
      return 1
    fi
    printf 'Waiting for [%s] to come up ...\\n' "$3"
    sleep 2
  done
}
""".replace("SCHEMA_AWAITED", str(AWAITED))


def resolve(module_name, fallbacks=()):
    return resolved(module_name, (
        ("BROKER_SERVICE", ("{}_BROKER_SERVICE".format(module_name.upper()),) + tuple(fallbacks) + (TARGET,)),
        ("BROKER_PORT", ("{}_BROKER_PORT".format(module_name.upper()), "VERNEMQ_API_PORT")),
    ))


def connect(module_name):
    return resolve(module_name) + CONNECT


def artifacts(source, module_name, options):
    return (_artifacts_discovered(source, module_name) if isinstance(source, SchemaDocument)
            else _artifacts_declared(source, module_name, options))


def ship(source, module_name, module_root, schemas_dir, options):
    working_dir = options.working_dir
    shipped_dir = join(str(working_dir), SHIPPED)
    publish_path = abspath(join(str(working_dir), SHIPPED + ".sh"))
    if exists(shipped_dir):
        shutil.rmtree(shipped_dir)
    if exists(publish_path):
        os.remove(publish_path)
    recovery = _recovery(module_root)
    metadata_df = None if isinstance(source, SchemaDocument) or len(source) == 0 else source
    if metadata_df is None and not recovery:
        return
    for _, row in [] if metadata_df is None else metadata_df.iterrows():
        discovery_dir = abspath(join(shipped_dir, str(row["discovery_topic"])))
        os.makedirs(discovery_dir)
        discovery_path = abspath(join(discovery_dir, str(row["unique_id"]) + ".json"))
        with open(discovery_path, 'w') as discovery_file:
            discovery_file.write(discovery(row))
        print("Build generate script [{}] entity metadata [sensor.{}] persisted to [{}]"
              .format(module_name, row["unique_id"], discovery_path))
    with open(publish_path, 'w') as publish_file:
        publish_file.write(publish_script(module_name, options.topic_glob_discovery, options.topic_glob_data,
                                          published=metadata_df is not None, recovery=recovery))
    os.chmod(publish_path, 0o750)
    print("Build generate script [{}] entity metadata publish script persisted to [{}]{}"
          .format(module_name, publish_path, " with a recovery fragment" if recovery else ""))


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


def _recovery(module_root):
    recovery_path = join(str(module_root), "src/build/resources", SHIPPED + ".sh")
    if not exists(recovery_path):
        return ""
    return "\n".join(line.rstrip() for line in open(recovery_path).read().splitlines()).strip()


def publish_script(module_name, topic_glob_discovery, topic_glob_data, published=True, recovery=""):
    globs_data = _glob_list(topic_glob_data)
    if published and not globs_data:
        raise ValueError(
            "Build generate script [{}] declares entities but no topic_glob_data, so the sweep would drop every "
            "retained topic on the broker: declare the module's own data topics".format(module_name))
    glob_data_args = " ".join('-t "{}"'.format(one) for one in globs_data)
    topic_find_discovery = ("*/" + topic_glob_discovery.replace("+", "*").replace("#", "*") + "/*" if topic_glob_discovery else "*")
    header = """
#!/usr/bin/env bash
{banner}

ROOT_DIR="$(dirname "$(readlink -f "$0")")/{shipped}"

ENV_DIR="$ROOT_DIR"
while [ "$ENV_DIR" != "/" ] && [ ! -f "$ENV_DIR/.env" ]; do ENV_DIR="$(dirname "$ENV_DIR")"; done
# shellcheck disable=SC1091
[ -f "$ENV_DIR/.env" ] && . "$ENV_DIR/.env"

SCHEMA_PHASE="${{1:-all}}"
case "${{SCHEMA_PHASE}}" in
sweep | publish | all) ;;
*)
  echo "Usage: $(basename "$0") [sweep|publish]" >&2
  exit 2
  ;;
esac
{resolve}
BROKER_ARGS=(-h "$BROKER_SERVICE" -p "$BROKER_PORT")
""".format(banner=banner(), shipped=SHIPPED, resolve=resolve(module_name))
    publish = """
if [ "${{SCHEMA_PHASE}}" != "publish" ]; then

printf '\\nEntity Metadata publish script [{module}] dropping discovery topics on [%s]:\\n' "$BROKER_SERVICE"
mosquitto_sub "${{BROKER_ARGS[@]}}" -F '%t' -t "{glob_discovery}" -W 5 2>/dev/null | sort -u | \\
  while read -r TOPIC; do
    printf '%s\\n' "$TOPIC"
    mosquitto_pub "${{BROKER_ARGS[@]}}" -t "$TOPIC" -r -n
  done
mosquitto_sub "${{BROKER_ARGS[@]}}" --remove-retained -F '%t' -t "{glob_discovery}" -W 5 2>/dev/null

printf '\\nEntity Metadata publish script [{module}] sleeping before dropping data topics ... ' && sleep 2 && printf 'done\\n\\n'

printf 'Entity Metadata publish script [{module}] dropping data topics on [%s]:\\n' "$BROKER_SERVICE"
mosquitto_sub "${{BROKER_ARGS[@]}}" --remove-retained -F '%t' {glob_data} -W 1 2>/dev/null

printf '\\nEntity Metadata publish script [{module}] sleeping before publishing discovery topics ... ' && sleep 2 && printf 'done\\n\\n'

fi

if [ "${{SCHEMA_PHASE}}" != "sweep" ]; then

printf 'Entity Metadata publish script [{module}] publishing discovery topics on [%s]:\\n' "$BROKER_SERVICE"
find "$ROOT_DIR" -path "{find_discovery}" -name "*.json" -print0 | sort -z | while read -r -d $'\\0' METADATA_FILE; do
  METADATA_TOPIC=$(dirname "${{METADATA_FILE/$ROOT_DIR\\//}}")
  mosquitto_pub "${{BROKER_ARGS[@]}}" -t "$METADATA_TOPIC" -f "$METADATA_FILE" -r
  printf '%s\\n' "$METADATA_TOPIC"
done
printf '\\n'

fi
""".format(
        module=module_name,
        glob_discovery=topic_glob_discovery,
        glob_data=glob_data_args,
        find_discovery=topic_find_discovery,
    ) if published else ""
    return "\n\n".join(part for part in (header.strip(), publish.strip(), recovery) if part) + "\n"


INSTANCE = """
levelled() {
  cut -d/ -f1-"$1" | sort | uniq -c | sort -rn |
    sed -e 's/^ *//' -e 's/ /\\t/'
}

SWEEP="$(topics '#')"

section "namespaces"
printf '%s\\n' "${SWEEP}" | sed -e '/^$/d' | levelled 1 |
  jq -R 'split("\\t") | {namespace: .[1], topics: (.[0] | tonumber)}' | table
printf '\\n'

section "scopes"
printf '%s\\n' "${SWEEP}" | sed -e '/^$/d' | levelled 2 |
  jq -R 'split("\\t") | {scope: .[1], topics: (.[0] | tonumber)}' | table
printf '\\n'
"""


def instance(module_name, zone=""):
    return instance_runner(module_name, DIALECT, "BROKER_SERVICE", connect(module_name), INSTANCE)


def describe_script(module_name, globs):
    return script(module_name, DIALECT, "describe", "print what the production broker actually retains",
                  connect(module_name), """
printf '\\nSchema describe [%s] against [%s]\\n' "{}" "${{BROKER_SERVICE}}"
{}
""".format(module_name, "\n".join(
        "printf -- '\\n-- %s\\n\\n' \"{}\"\ntopics {} | listed\nprintf '\\n'".format(_expand(glob), _arguments(glob))
        for glob in globs)))


def query_script(module_name):
    return script(module_name, DIALECT, "query", "print the retained payload of every declared topic",
                  connect(module_name), """
printf '\\nSchema query [%s] against [%s]\\n' "{}" "${{BROKER_SERVICE}}"
while IFS= read -r TOPIC; do
  printf -- '\\n-- %s\\n\\n' "${{TOPIC}}"
  payload "${{TOPIC}}"
  printf '\\n'
done < <(declared)
""".format(module_name))


def verify_script(module_name, globs, commands):
    return script(module_name, DIALECT, "verify", "assert the broker retains exactly the declared topics",
                  connect(module_name), """
printf '\\nSchema verify [%s] against [%s]\\n' "{}" "${{BROKER_SERVICE}}"
printf -- '\\n-- %s\\n\\n' "verify"

COMMAND_TOPICS=({})

FAULT_FILE="$(mktemp)"
RETAINED_FILE="$(mktemp)"
DECLARED_FILE="$(mktemp)"
COMMAND_FILE="$(mktemp)"
trap 'rm -f "${{FAULT_FILE}}" "${{RETAINED_FILE}}" "${{DECLARED_FILE}}" "${{COMMAND_FILE}}"' EXIT

declared > "${{DECLARED_FILE}}"
printf '%s\\n' ${{COMMAND_TOPICS[@]+"${{COMMAND_TOPICS[@]}}"}} | sed '/^$/d' | sort -u > "${{COMMAND_FILE}}"

{}
sort -u -o "${{RETAINED_FILE}}" "${{RETAINED_FILE}}"
sort -u -o "${{DECLARED_FILE}}" "${{DECLARED_FILE}}"

comm -23 "${{DECLARED_FILE}}" "${{COMMAND_FILE}}" | comm -23 - "${{RETAINED_FILE}}" |
  while IFS= read -r TOPIC; do faulted "${{TOPIC}}" missing; done >> "${{FAULT_FILE}}"
comm -13 "${{DECLARED_FILE}}" "${{RETAINED_FILE}}" |
  while IFS= read -r TOPIC; do faulted "${{TOPIC}}" undeclared; done >> "${{FAULT_FILE}}"
FAULTS="$(grep -c . "${{FAULT_FILE}}" || true)"

if [ "${{FAULTS}}" != "0" ]; then
  table < "${{FAULT_FILE}}"
  printf '\\n'
  printf '\\nSchema verify [%s] found [%s] fault row(s)\\n' "{}" "${{FAULTS}}" >&2
  exit 1
fi
printf '\\nSchema verify [%s] found no drift\\n' "{}"
""".format(module_name, " ".join('"{}"'.format(command) for command in commands), "\n".join(
        'topics {} >> "${{RETAINED_FILE}}"'.format(_arguments(glob)) for glob in globs), module_name, module_name))


class Discover:

    def __init__(self, glob, module=None, label="", target=None, port=None,
                 timeout=TIMEOUT, module_root=None):
        self.module = basename(module_root or load_bootstrap_root()) if module is None else module
        self.glob = glob
        self.label = label
        self.timeout = timeout
        self.target = target or self._env(TARGET, module_root)
        self.port = port or self._env("VERNEMQ_API_PORT", module_root)
        if not self.target or not self.port:
            raise ValueError("Build generate script [{}] vernemq discovery found no target [{}] or port [{}] "
                             "in the module env file [{}]".format(self.module, self.target, self.port, ENV))

    def document(self):
        try:
            payloads = [self.payload(topic, retained) for topic, retained in sorted(self.retained().items())]
        except SchemaUnreachable as unreachable:
            print("Build generate script [{}] could not connect to {} with error [{}]"
                  .format(self.module, DIALECT, unreachable))
            return None
        return SchemaDocument(module=self.module, payloads=payloads, discovered=True, glob=self.glob)

    def retained(self):
        messages = {}
        for line in self.subscribe():
            try:
                message = json.loads(line)
            except ValueError:
                continue
            topic = message.get("topic")
            if topic and message.get("retain"):
                messages[topic] = message.get("payload")
        return messages

    def subscribe(self):
        command = ["mosquitto_sub", "-h", str(self.target), "-p", str(self.port),
                   "-F", "%J", "-t", self.glob, "-W", str(self.timeout)]
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=self.timeout * 4)
        except (OSError, subprocess.SubprocessError) as exception:
            raise SchemaUnreachable(exception) from exception
        if not completed.stdout.strip() and completed.returncode not in (0, 27):
            raise SchemaUnreachable(completed.stderr.strip() or
                                    "mosquitto_sub exited [{}]".format(completed.returncode))
        return completed.stdout.splitlines()

    def payload(self, topic, retained):
        return SchemaBrokerPayload(role=DISCOVERED, match=topic, root=self.member("", retained))

    def member(self, key, value):
        if isinstance(value, dict):
            return SchemaBrokerMember(key=key, members=[self.member(nested, value[nested]) for nested in value])
        return SchemaBrokerMember(key=key, kind=self.kind(value))

    @staticmethod
    def kind(value):
        if isinstance(value, bool):
            return "bool"
        if isinstance(value, int):
            return "int"
        if isinstance(value, float):
            return "float"
        return "str"

    @staticmethod
    def _env(name, module_root):
        return load_bootstrap_env_value(name, filename=ENV, module_root=module_root)


def config_script(module_name, name, summary, health_topic, health_filter, commands, preamble=""):
    return script(module_name, SHIPPED, name, summary,
                  resolve(module_name, ("VERNEMQ_SERVICE",)) + CONFIG + preamble, """
printf '\\nBroker {} [%s] against [%s]\\n\\n' "{}" "${{BROKER_SERVICE}}"

awaited "{}" '{}' "{}" || exit 1

{}
""".format(name, module_name, health_topic, health_filter, module_name, "\n".join(commands)), env_required=False)


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
        if payload.match == topic:
            return render(payload.root)
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


def _declared_topics(module_name, options):
    document = options.document
    if document is None or not getattr(document, "topics", None):
        return []
    declared_globs = _glob_list(options.topic_glob_data) + _glob_list(options.topic_glob_verify)
    bindings = _bindings(module_name, options.entities)
    declared = {}
    for topic in document.topics:
        expanded = _expanded(module_name, topic.template, bindings)
        if not expanded:
            raise ValueError(
                "Build generate script [{}] topic template [{}] expanded to nothing, supply broker_entities "
                "binding every placeholder it names".format(module_name, topic.template))
        for value in expanded:
            if declared_globs and not _glob_match_any(declared_globs, value):
                raise ValueError(
                    "Build generate script [{}] declared globs {} do not match declared topic [{}] from "
                    "template [{}]: update the glob or the declaration so they agree"
                    .format(module_name, declared_globs, value, topic.template))
            declared[value] = topic.role
    return sorted(declared.items())


def _bindings(module_name, entities):
    if entities is None:
        return [{}]
    if isinstance(entities, dict):
        entities = [entities]
    bindings = []
    for entity in entities:
        if not isinstance(entity, dict):
            raise ValueError("Build generate script [{}] broker_entities must be a mapping or a list of mappings, "
                             "got [{}]".format(module_name, type(entity).__name__))
        bindings.append({str(name): ([str(value)] if isinstance(value, str) else [str(each) for each in value])
                         for name, value in entity.items()})
    return bindings


def _expanded(module_name, template, bindings):
    expanded = []
    for binding in bindings:
        names = sorted(set(BINDING.findall(template)))
        missing = [name for name in names if name not in binding]
        if missing:
            raise ValueError(
                "Build generate script [{}] topic template [{}] names placeholder(s) {} that broker_entities "
                "does not bind".format(module_name, template, missing))
        rendered = [template]
        for name in names:
            rendered = [candidate.replace("$" + name, value)
                        for candidate in rendered for value in binding[name]]
        expanded.extend(rendered)
    return sorted(set(expanded))


def _glob_list(topic_glob):
    if not topic_glob:
        return []
    if isinstance(topic_glob, str):
        return [topic_glob]
    return list(topic_glob)


def _glob_match_any(topic_glob, topic):
    return any(_glob_match(one, topic) for one in _glob_list(topic_glob))


def _validate_globs(metadata_df, module_name, topic_glob_discovery, topic_glob_data):
    for topic_glob, topic_glob_name, topic_glob_columns in (
            (topic_glob_discovery, "topic_glob_discovery", ("discovery_topic",)),
            (topic_glob_data, "topic_glob_data", ("state_topic", "command_topic", "availability_topic"))):
        for topic_glob_column in topic_glob_columns:
            unmatched = [topic for topic in _column_topics(metadata_df, topic_glob_column)
                         if not _glob_match_any(topic_glob, topic)]
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


def _discoveries(metadata_df):
    if "discovery_topic" not in metadata_df.columns:
        return {}
    return {str(row["discovery_topic"]).strip(): row for _, row in metadata_df.iterrows()
            if str(row["discovery_topic"]).strip()}


def _column_topics(metadata_df, column):
    if column not in metadata_df.columns:
        return []
    return sorted({topic.strip() for topic in metadata_df[column].dropna().unique() if topic.strip()})


def _artifacts_declared(metadata_df, module_name, options):
    _validate_globs(metadata_df, module_name, options.topic_glob_discovery, options.topic_glob_data)
    topics = _topics(metadata_df)
    specs = _specs(module_name, options)
    declared = _declared_topics(module_name, options)
    if not topics and not declared:
        return {}
    document = options.document
    globs = [glob for glob in ([options.topic_glob_discovery] + _glob_list(options.topic_glob_data) + _glob_list(options.topic_glob_verify)) if glob]
    discoveries = _discoveries(metadata_df)
    generated = {}
    for column, column_topics in topics.items():
        role = ROLE_COLUMNS.get(column, "") if document is not None else ""
        for topic in column_topics:
            payload = (discovery(discoveries[topic]) if column == "discovery_topic" and topic in discoveries
                       else leaf(topic, specs.get(column, ""), document, role))
            generated["model/{}/{}".format(topic, LEAF)] = (payload, False)
    for topic, role in declared:
        path = "model/{}/{}".format(topic, LEAF)
        if path in generated:
            continue
        generated[path] = (leaf(topic, None, document, role), False)
    generated["describe.sh"] = (describe_script(module_name, globs), True)
    generated["query.sh"] = (query_script(module_name), True)
    generated["verify.sh"] = (
        verify_script(module_name, globs, sorted(topics.get("command_topic", []))), True)
    return generated


def _artifacts_discovered(document, module_name):
    topics = sorted({payload.match for payload in document.payloads if payload.match})
    if not topics:
        return {}
    generated = {}
    for topic in topics:
        generated["model/{}/{}".format(topic, LEAF)] = (leaf(topic, None, document, DISCOVERED), False)
    globs = [document.glob] if document.glob else []
    generated["describe.sh"] = (describe_script(module_name, globs), True)
    generated["query.sh"] = (query_script(module_name), True)
    return generated


def _topics(metadata_df):
    topics = {column: _column_topics(metadata_df, column) for column in TOPIC_COLUMNS}
    return {column: column_topics for column, column_topics in topics.items() if column_topics}


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
                    "Build generate script [{}] role [{}] is declared in code and also passed as a literal [{}], "
                    "supply one or the other, never both".format(module_name, role, column))
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
