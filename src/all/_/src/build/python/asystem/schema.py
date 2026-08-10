import importlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field, fields, is_dataclass
from os.path import *

from asystem.bootstrap import load_bootstrap_env_value, load_bootstrap_root

DIALECTS = ("influxdb3", "postgres")
KINDS = ("float", "int", "bool", "str")
ROLES = ("state", "command", "availability")
TYPES = {
    str: "text",
    list: "an array",
    dict: "an object",
    bool: "true or false",
}


@dataclass
class SchemaDatabaseDimension:
    key: str
    description: str = ""
    subject: bool = False


@dataclass
class SchemaDatabaseMeasure:
    key: str
    kind: str
    unit: str = ""
    description: str = ""
    persist: bool = True
    period: str = ""


@dataclass
class SchemaDatabaseRelation:
    path: str
    description: str = ""
    cadence: str = ""
    entities: list = field(default_factory=list)
    dimensions: list = field(default_factory=list)
    measures: list = field(default_factory=list)

    @property
    def plugin(self):
        return self.path.split("/", 1)[0]

    @property
    def scope(self):
        return self.path.split("/", 1)[1] if "/" in self.path else ""

    @property
    def subject(self):
        return next((dimension for dimension in self.dimensions if dimension.subject), None)

    @property
    def persisted(self):
        return [measure for measure in self.measures if measure.persist and measure.kind in ("float", "int", "bool")]

    def span(self, measure):
        return measure.period or self.cadence


@dataclass
class SchemaBrokerMember:
    key: str = ""
    kind: str = "str"
    enum: list = field(default_factory=list)
    members: list = field(default_factory=list)


@dataclass
class SchemaBrokerPayload:
    role: str
    match: str = ""
    root: SchemaBrokerMember = field(default_factory=SchemaBrokerMember)


@dataclass
class SchemaDocument:
    module: str
    relations: list = field(default_factory=list)
    payloads: list = field(default_factory=list)


def load_schema_document(module_root=None, config=None, args=None):
    """Reflect a module's schema declaration into a SchemaDocument.

    A module declares its broker and database schema, opting in via a reflector in known locations,
    dispatched on module contents, first match wins:

    src/main/python/<module>/plugin/schema.py   Imported in process, it's optional [database_schema] and
                                                [broker_schema] called with [config] when the caller passes
                                                one and with nothing when it does not, returning objects

    src/main/go/<module>/tools/schema/          A [main] package of its own, run as [go run ./tools/schema],
                                                printing a schema document

    src/main/rust/<module>/tools/schema/        A workspace member crate of its own, named in the service
                                                crate [workspace] members and depending on it by path, run
                                                as [cargo run --manifest-path tools/schema/Cargo.toml],
                                                printing a schema document

    The go/rust tools are handed [--config <path>] and [args] as flags, printing a schema document with spec:

    {
        "module":      "<name>",            OPTIONAL  Owning module, defaults to the module directory name
        "database":    {                    OPTIONAL  What the service writes to a database backend
          "relations":   [{                 OPTIONAL  One per distinct row shape written
            "path":        "<path>",        REQUIRED  [<plugin>/<scope>], [<plugin>] is what the backend writes to
            "description": "<text>",        OPTIONAL  What the relation holds
            "cadence":     "<duration>",    OPTIONAL  How often a row arrives, never written, sizes buckets and windows
            "entities":    ["<entity>"],    OPTIONAL  Values the subject takes, generate.py may fill them instead
            "dimensions":  [{               OPTIONAL  What identifies a row
              "key":         "<name>",      REQUIRED  Name of the dimension, each backend projects it its own way
              "description": "<text>",      OPTIONAL  What the dimension distinguishes
              "subject":     <true|false>   OPTIONAL  The entity axis, at most one per relation, defaults to false
            }],
            "measures":    [{               OPTIONAL  What a row carries
              "key":         "<name>",      REQUIRED  Name of the measure, each backend projects it its own way
              "kind":        "<kind>",      REQUIRED  Value type
              "unit":        "<text>",      OPTIONAL  Unit of the value, e.g. [%] [$] [celsius] [seconds]
              "description": "<text>",      OPTIONAL  What the measure records
              "persist":     <true|false>,  OPTIONAL  Declared but never written when false, defaults to true
              "period":      "<duration>"   OPTIONAL  Span the value covers, part of the row key, defaults to cadence
            }]
          }]
        },
        "broker":      {                    OPTIONAL  What the service publishes to the broker
          "payloads":    [{                 OPTIONAL  One per payload shape published
            "role":        "<role>",        REQUIRED  [state|command|availability], the xlsx topic column filled
            "match":       "<topic-glob>",  OPTIONAL  Picks between payloads sharing a role, matched by fnmatch
            "root":        <member>         OPTIONAL  Payload shape rendered to the topic leaf
          }]
        }
    }

    A [<kind>] is one of [float] [int] [bool] [str].

    A [<duration>] is an unsigned integer and a unit suffix, one of [s] [m] [h] [d], e.g. [30s] [15m] [1d].

    A [<member>], nesting arbitrarily deep through its own [members]:

    {
        "key":         "<name>",            OPTIONAL  Member name, empty for the root of a bare payload
        "kind":        "<kind>",            OPTIONAL  Scalar type, ignored when [members] or [enum] is set
        "enum":        ["<option>"],        OPTIONAL  Renders as [<a|b|c>] in place of the kind placeholder
        "members":     [<member>]           OPTIONAL  Nested members, which make this an object
    }
    """
    if module_root is None:
        module_root = load_bootstrap_root()
    module_name = basename(module_root)
    if config is not None and not isabs(config):
        config = abspath(join(module_root, config))
    python_path = join(module_root, "src/main/python", module_name, "plugin/schema.py")
    go_path = join(module_root, "src/main/go", module_name, "tools/schema")
    rust_path = join(module_root, "src/main/rust", module_name, "tools/schema")
    if isfile(python_path):
        document = _load_schema_python(module_root, module_name, python_path, config)
    elif isdir(go_path):
        document = _parse_document(_run_schema_go(module_root, module_name, config, args), module_name)
    elif isdir(rust_path):
        document = _parse_document(_run_schema_rust(module_root, module_name, config, args), module_name)
    else:
        raise ValueError("Build generate script [{}] declares no schema reflector, expected one of [{}] [{}] [{}]"
                         .format(module_name, python_path, go_path, rust_path))
    print("Build generate script [{}] schema reflected with relations [{}] payloads [{}]"
          .format(module_name, len(document.relations), len(document.payloads)))
    sys.stdout.flush()
    return document


def merge_schema_entities(document, entities=None):
    if not entities:
        return document
    relations = {relation.path: relation for relation in document.relations}
    for path, subjects in entities.items():
        if path not in relations:
            raise ValueError("Build generate script [{}] entities supplied for undeclared relation [{}]"
                             .format(document.module, path))
        relation = relations[path]
        subjects = [str(subject) for subject in subjects]
        if relation.entities and sorted(relation.entities) != sorted(subjects):
            raise ValueError(
                "Build generate script [{}] relation [{}] declares entities {} but the emitter was passed {}: "
                "the code declaration wins, so make them agree or drop the override"
                .format(document.module, path, sorted(relation.entities), sorted(subjects)))
        relation.entities = subjects
    return document


def _load_schema_python(module_root, module_name, python_path, config):
    sources_dir = join(module_root, "src/main/python")
    if sources_dir not in sys.path:
        sys.path.insert(0, sources_dir)
    try:
        module = importlib.import_module("{}.plugin.schema".format(module_name))
    except ImportError as error:
        raise ValueError("Build generate script [{}] could not import schema module [{}] [{}]"
                         .format(module_name, python_path, error))
    document = SchemaDocument(module=module_name)
    if hasattr(module, "database_schema"):
        document.relations = list(module.database_schema(config) if config is not None else module.database_schema())
    if hasattr(module, "broker_schema"):
        document.payloads = list(module.broker_schema(config) if config is not None else module.broker_schema())
    _validate(document)
    return document


def _run_schema_go(module_root, module_name, config, args=None):
    go_version = load_bootstrap_env_value("ASYSTEM_GO_VERSION", filename=".env", module_root=module_root)
    go_root = join(os.environ["HOME"], ".goenv/versions", go_version)
    go_binary = join(go_root, "bin/go")
    if not isfile(go_binary):
        raise ValueError("Build generate script [{}] go binary not found [{}]".format(module_name, go_binary))
    command = [go_binary, "run", "-mod=readonly", "./tools/schema"]
    if config is not None:
        command += ["--config", config]
    command += list(args or [])
    return _run(module_name, command, join(module_root, "src/main/go", module_name), {
        "GOROOT": go_root,
        "GOPATH": abspath(join(module_root, "../../../.go")),
        "PATH": join(go_root, "bin") + os.pathsep + os.environ.get("PATH", ""),
    })


def _run_schema_rust(module_root, module_name, config, args=None):
    rust_version = load_bootstrap_env_value("ASYSTEM_RUST_VERSION", filename=".env", module_root=module_root)
    cargo_home = join(os.environ["HOME"], ".rust/versions/asystem")
    cargo_binary = join(cargo_home, "bin/cargo")
    if not isfile(cargo_binary):
        raise ValueError("Build generate script [{}] cargo binary not found [{}]".format(module_name, cargo_binary))
    command = [cargo_binary, "run", "--quiet", "--manifest-path", "tools/schema/Cargo.toml", "--"]
    if config is not None:
        command += ["--config", config]
    command += list(args or [])
    return _run(module_name, command, join(module_root, "src/main/rust", module_name), {
        "CARGO_HOME": cargo_home,
        "RUSTUP_HOME": cargo_home,
        "CARGO_TARGET_DIR": join(module_root, "target/rust"),
        "RUSTUP_TOOLCHAIN": rust_version,
        "PATH": join(cargo_home, "bin") + os.pathsep + os.environ.get("PATH", ""),
    })


def _run(module_name, command, working_dir, overrides):
    env = dict(os.environ)
    env.update({key: value for key, value in overrides.items() if value})
    try:
        completed = subprocess.run(command, cwd=working_dir, env=env, check=True, capture_output=True, text=True, timeout=120)
    except subprocess.CalledProcessError as error:
        raise ValueError("Build generate script [{}] schema reflection failed [{}] in [{}] with [{}]"
                         .format(module_name, " ".join(command), working_dir, error.stderr.strip()))
    except subprocess.TimeoutExpired:
        raise ValueError("Build generate script [{}] schema reflection timed out [{}] in [{}]"
                         .format(module_name, " ".join(command), working_dir))
    if completed.stderr.strip():
        print(completed.stderr.strip(), file=sys.stderr)
    return completed.stdout


def _parse_document(text, module_name):
    """Parse and validate a reflected document, the private half of the contract on [load_schema_document].
    """
    try:
        parsed = json.loads(text)
    except ValueError as error:
        raise ValueError("Build generate script [{}] schema reflection emitted unparseable JSON [{}]"
                         .format(module_name, error))
    _reject_unknown(module_name, "document", parsed, ("module", "database", "broker"))
    database = _mapping(module_name, "document", parsed, "database")
    broker = _mapping(module_name, "document", parsed, "broker")
    _reject_unknown(module_name, "database", database, ("relations",))
    _reject_unknown(module_name, "broker", broker, ("payloads",))
    document = SchemaDocument(
        module=_text(module_name, "document", parsed, "module", module_name),
        relations=[_parse_relation(module_name, relation) for relation in _mappings(module_name, "database", database, "relations")],
        payloads=[_parse_payload(module_name, payload) for payload in _mappings(module_name, "broker", broker, "payloads")])
    _validate(document)
    return document


def _parse_relation(module_name, relation):
    scope = _scope("", "relation", relation, "path")
    _reject_unknown(module_name, scope, relation, SchemaDatabaseRelation)
    return SchemaDatabaseRelation(
        path=_text(module_name, scope, relation, "path"),
        description=_text(module_name, scope, relation, "description", ""),
        cadence=_text(module_name, scope, relation, "cadence", ""),
        entities=_texts(module_name, scope, relation, "entities"),
        dimensions=[_parse_dimension(module_name, scope, dimension) for dimension in _mappings(module_name, scope, relation, "dimensions")],
        measures=[_parse_measure(module_name, scope, measure) for measure in _mappings(module_name, scope, relation, "measures")])


def _parse_dimension(module_name, scope, dimension):
    scope = _scope(scope, "dimension", dimension)
    _reject_unknown(module_name, scope, dimension, SchemaDatabaseDimension)
    return SchemaDatabaseDimension(
        key=_text(module_name, scope, dimension, "key"),
        description=_text(module_name, scope, dimension, "description", ""),
        subject=_flag(module_name, scope, dimension, "subject", False))


def _parse_measure(module_name, scope, measure):
    scope = _scope(scope, "measure", measure)
    _reject_unknown(module_name, scope, measure, SchemaDatabaseMeasure)
    return SchemaDatabaseMeasure(
        key=_text(module_name, scope, measure, "key"),
        kind=_text(module_name, scope, measure, "kind"),
        unit=_text(module_name, scope, measure, "unit", ""),
        description=_text(module_name, scope, measure, "description", ""),
        persist=_flag(module_name, scope, measure, "persist", True),
        period=_text(module_name, scope, measure, "period", ""))


def _parse_payload(module_name, payload):
    scope = _scope("", "payload", payload, "role")
    _reject_unknown(module_name, scope, payload, SchemaBrokerPayload)
    return SchemaBrokerPayload(
        role=_text(module_name, scope, payload, "role"),
        match=_text(module_name, scope, payload, "match", ""),
        root=_parse_member(module_name, scope, _mapping(module_name, scope, payload, "root")))


def _parse_member(module_name, scope, member):
    scope = _scope(scope, "member", member)
    _reject_unknown(module_name, scope, member, SchemaBrokerMember)
    return SchemaBrokerMember(
        key=_text(module_name, scope, member, "key", ""),
        kind=_text(module_name, scope, member, "kind", "str"),
        enum=_texts(module_name, scope, member, "enum"),
        members=[_parse_member(module_name, scope, nested) for nested in _mappings(module_name, scope, member, "members")])


def _scope(scope, noun, mapping, key="key"):
    return "{}{} [{}]".format(scope + " " if scope else "", noun, mapping.get(key, "") if isinstance(mapping, dict) else "")


def _reject_unknown(module_name, scope, mapping, allowed):
    if is_dataclass(allowed):
        allowed = tuple(declared.name for declared in fields(allowed))
    if not isinstance(mapping, dict):
        raise ValueError("Build generate script [{}] schema reflection emitted non-object [{}] [{}]"
                         .format(module_name, scope, type(mapping).__name__))
    unknown = sorted(key for key in mapping if key not in allowed)
    if unknown:
        raise ValueError("Build generate script [{}] schema reflection emitted unknown [{}] key(s) [{}] expected [{}]"
                         .format(module_name, scope, ",".join(unknown), ",".join(allowed)))


def _text(module_name, scope, mapping, key, default=None):
    return _value(module_name, scope, mapping, key, str, default)


def _texts(module_name, scope, mapping, key):
    return list(_value(module_name, scope, mapping, key, list, [], element=str))


def _flag(module_name, scope, mapping, key, default):
    return _value(module_name, scope, mapping, key, bool, default)


def _mapping(module_name, scope, mapping, key):
    return _value(module_name, scope, mapping, key, dict, {})


def _mappings(module_name, scope, mapping, key):
    return _value(module_name, scope, mapping, key, list, [])


def _value(module_name, scope, mapping, key, kind, default=None, element=None):
    value = mapping.get(key)
    value = default if value is None else value
    if value is None:
        raise ValueError("Build generate script [{}] schema reflection {} requires key [{}]"
                         .format(module_name, scope, key))
    if not isinstance(value, kind):
        raise ValueError("Build generate script [{}] schema reflection {} emitted key [{}] as [{}] expected [{}]"
                         .format(module_name, scope, key, type(value).__name__, TYPES[kind]))
    if element is not None:
        for item in value:
            if not isinstance(item, element):
                raise ValueError("Build generate script [{}] schema reflection {} emitted key [{}] element [{}] "
                                 "as [{}] expected [{}]".format(module_name, scope, key, item, type(item).__name__, TYPES[element]))
    return value


def _validate(document):
    paths = set()
    for relation in document.relations:
        if "/" not in relation.path:
            raise ValueError("Build generate script [{}] relation path must be [<plugin>/<scope>] [{}]"
                             .format(document.module, relation.path))
        if relation.path in paths:
            raise ValueError("Build generate script [{}] duplicate relation [{}]".format(document.module, relation.path))
        paths.add(relation.path)
        if len([dimension for dimension in relation.dimensions if dimension.subject]) > 1:
            raise ValueError("Build generate script [{}] relation [{}] declares more than one subject dimension"
                             .format(document.module, relation.path))
        for measure in relation.measures:
            if measure.kind not in KINDS:
                raise ValueError("Build generate script [{}] relation [{}] measure [{}] declares unknown kind [{}]"
                                 .format(document.module, relation.path, measure.key, measure.kind))
    for payload in document.payloads:
        if payload.role not in ROLES:
            raise ValueError("Build generate script [{}] payload declares unknown role [{}]"
                             .format(document.module, payload.role))
        _validate_member(document, payload.root)


def _validate_member(document, member):
    if member.kind not in KINDS:
        raise ValueError("Build generate script [{}] payload member [{}] declares unknown kind [{}]"
                         .format(document.module, member.key, member.kind))
    for nested in member.members:
        _validate_member(document, nested)


def write_schema_database(document, dialect="influxdb3", time_column="timestamp",
                          retention=None, entities=None, module_name=None, schemas_dir=None):
    if dialect not in DIALECTS:
        raise ValueError("Build generate script [{}] unknown dialect [{}] expected one of {}"
                         .format(document.module, dialect, list(DIALECTS)))
    module_root = load_bootstrap_root()
    if module_name is None:
        module_name = basename(module_root)
    if schemas_dir is None:
        schemas_dir = join(module_root, "src/build/resources/schema")
    merge_schema_entities(document, entities)
    from asystem import schema_influxdb, schema_postgres
    emitter = {schema_influxdb.DIALECT: schema_influxdb, schema_postgres.DIALECT: schema_postgres}[dialect]
    artifacts = emitter.artifacts(document, module_name, time_column, retention)
    write_schema_dialect(module_name, schemas_dir, dialect, artifacts)
    emitter.ship(document, module_name, module_root, schemas_dir, time_column)


def write_schema_broker(metadata_df, module_name=None, working_root=None, schemas_dir=None,
                        topic_glob_discovery=None, topic_glob_data=None, schema_state=None, schema_command=None, schema_availability=None, document=None):
    from asystem import schema_vernemq
    if len(metadata_df) == 0:
        return
    module_root = load_bootstrap_root()
    if module_name is None:
        module_name = basename(module_root)
    if working_root is None:
        working_root = join(module_root, "src/main/resources/image")
    if schemas_dir is None:
        schemas_dir = join(module_root, "src/build/resources/schema")
    artifacts = schema_vernemq.artifacts(metadata_df, module_name, topic_glob_discovery, topic_glob_data, schema_state, schema_command, schema_availability, document)
    if artifacts:
        write_schema_dialect(module_name, schemas_dir, schema_vernemq.DIALECT, artifacts)
    schema_vernemq.ship(metadata_df, module_name, working_root, topic_glob_discovery, topic_glob_data)


def banner(prefix="#"):
    rule = prefix * (80 // len(prefix))
    return "{0}\n{1} WARNING: This file is written by the build process, any manual edits will be lost!\n{0}".format(
        rule, prefix)


def vocabulary(relation, prefix="#", tags=()):
    lines = ["{} {} [{}]".format(prefix, relation.path, relation.description)]
    if relation.cadence:
        lines.append("{}   cadence {}".format(prefix, relation.cadence))
    for dimension in list(tags) + list(relation.dimensions):
        lines.append("{}   tag {}{} [{}]".format(
            prefix, dimension.key, SUBJECT if dimension.subject else "", dimension.description))
    if relation.subject is not None:
        lines += _entities(relation.entities, prefix)
    for measure in relation.measures:
        lines.append("{}   field {} {} {} [{}]{}".format(
            prefix, measure.key, UNITS.get(measure.unit, measure.unit) or NULL, relation.span(measure) or NULL,
            measure.description, "" if measure.persist else " (not persisted)"))
    return lines


def _entities(entities, prefix, width=110):
    leading = "{}   entity ".format(prefix)
    if not entities:
        return [leading + "<undeclared, whatever the service writes>"]
    lines, current = [], ""
    for index, entity in enumerate(entities):
        entity += "," if index < len(entities) - 1 else ""
        if current and len(leading) + len(current) + 1 + len(entity) > width:
            lines.append(leading + current)
            current = ""
        current += (" " if current else "") + entity
    return lines + [leading + current]


def select(selectors, source, predicates=(),
           group_by=(), having=(), order_by=(), limit=None, distinct_on=()):
    width = max([len(expression) for expression, alias in selectors if alias and "\n" not in expression] or [0])
    rendered = []
    for expression, alias in selectors:
        if "\n" in expression:
            wrapped = indent(expression)
            rendered.append("\n".join(wrapped[:-1] + ["{} AS {}".format(wrapped[-1], alias)] if alias else wrapped))
        else:
            rendered.append("    {} AS {}".format(expression.ljust(width), alias) if alias else "    {}".format(expression))
    lines = ["SELECT" + (" DISTINCT ON ({})".format(", ".join(distinct_on)) if distinct_on else "")]
    lines += [line + "," for line in rendered[:-1]] + rendered[-1:]
    lines.append("FROM {}".format(source))
    if predicates:
        lines.append("WHERE")
        for index, predicate in enumerate(predicates):
            lines += indent(predicate if index == 0 else "AND " + predicate)
    if group_by:
        lines.append("GROUP BY {}".format(", ".join(group_by)))
    if having:
        lines.append("HAVING {}".format(" AND ".join(having)))
    if order_by:
        lines.append("ORDER BY {}".format(", ".join(order_by)))
    if limit is not None:
        lines.append("LIMIT {}".format(limit))
    return "\n".join(lines)


RUNNER = r"""
SCHEMA_ECHO=${SCHEMA_ECHO:-true}
SCHEMA_ACTION=${SCHEMA_ACTION:-Describe}
SCHEMA_TARGET=${SCHEMA_TARGET:-}
SCHEMA_LABEL=${SCHEMA_LABEL:-}

statements() {
  sed -e 's/--.*$//' "$1" | tr '\n' ' ' | tr ';' '\n' |
    sed -e 's/[[:space:]][[:space:]]*/ /g' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//'
}

table() {
  jq -sr '
    def title: split("_") | map(if length > 0 then (.[0:1] | ascii_upcase) + .[1:] else . end) | join(" ");
    def numeric: type == "number" or (type == "string" and test("^-?[0-9]+([.][0-9]+)?$"));
    def placeholder: . == "-" or . == "";
    (if length == 1 and (.[0] | type) == "array" then .[0] else . end)
    | if length == 0 then "no rows" else
      (.[0] | keys_unsorted) as $columns
      | [range(0; $columns | length)] as $indexes
      | (map(. as $row | $columns
        | map(if $row[.] == null then "" else ($row[.] | tostring) end))) as $body
      | ([$columns | map(title)] + $body) as $matrix
      | ($indexes | map(. as $index | $matrix | map(.[$index] | length) | max)) as $widths
      | ($indexes | map(. as $index | $body | map(.[$index])
        | (any(numeric) and all(numeric or placeholder)))) as $rights
      | (def row($cells): "|" + ($cells | to_entries | map(
           ((" " * ($widths[.key] - (.value | length))) // "") as $fill
           | if $rights[.key] then " " + $fill + .value + " " else " " + .value + $fill + " " end)
           | join("|")) + "|";
         def rule: "+" + ($indexes | map("-" * ($widths[.] + 2)) | join("+")) + "+";
         [rule, row($matrix[0]), rule] + ($body | map(row(.))) + [rule] | join("\n"))
    end
  '
}

query_block() {
  local block="$1" statement label result
  statement="$(printf '%s\n' "${block}" | sed -e 's/--.*$//' | tr '\n' ' ' |
    sed -e 's/[[:space:]][[:space:]]*/ /g' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*;*[[:space:]]*$//')"
  [ -z "${statement}" ] && return 0
  if [ -n "${SCHEMA_LABEL}" ]; then
    printf -- '-- %s\n' "${SCHEMA_LABEL}"
  fi
  if [ "${SCHEMA_ECHO}" = true ]; then
    printf '%s\n\n' "${block}"
  else
    label="$(printf '%s\n' "${block}" | sed -n -e 's/^-- //p' | head -1)"
    printf '%s [%s] against [%s]:\n\n' "${SCHEMA_ACTION}" "${label}" "${SCHEMA_TARGET}"
  fi
  if ! result="$(query "${statement}")"; then
    fail "${statement}" "${result}"
    return 1
  fi
  printf '%s\n' "${result}" | table
  printf '\n'
}

fail() {
  printf '\n%s\n%s\n%s\n\n%s\n\n%s\n\n' \
    "################################################################################" \
    "SCHEMA FAILURE" \
    "################################################################################" \
    "$1" "$2" >&2
}

query_one() {
  local result
  if ! result="$(query "$1")"; then
    fail "$1" "${result}"
    return 1
  fi
  printf '%s\n' "${result}" | table
}

rows() {
  jq -s '(if length == 1 and (.[0] | type) == "array" then .[0] else . end) | length'
}

query_file() {
  local line block="" faults=0
  while IFS= read -r line || [ -n "${line}" ]; do
    case "${line}" in
    ---*) continue ;;
    "-- WARNING:"*) continue ;;
    esac
    [ -z "${block}" ] && [ -z "${line}" ] && continue
    block="${block}${line}"$'\n'
    case "${line}" in
    *\;)
      query_block "${block%$'\n'}" || faults=$((faults + 1))
      block=""
      ;;
    esac
  done < "$1"
  if [ -n "${block}" ]; then
    query_block "${block%$'\n'}" || faults=$((faults + 1))
  fi
  [ "${faults}" = 0 ]
}
"""

NULL = "-"
YES = "yes"
NO = "no"
SUBJECT = "*"
UNITS = {"celsius": "Celsius"}
ALIAS = 4
SPELLED = 6
CROWDED = 5
ABBREVIATED = False
WIDTH = 300
CELL = 8
KEYED = 15
STAMPED = 19
SAMPLES = 100
GUARD = 100
VOWELS = "aeiou"
BUCKET = "1 day"
BUCKETS = ("1 minute", "5 minute", "15 minute", "1 hour", "6 hour", "1 day")
DURATIONS = {
    "s": 1,
    "sec": 1,
    "second": 1,
    "m": 60,
    "min": 60,
    "minute": 60,
    "h": 3600,
    "hour": 3600,
    "d": 86400,
    "day": 86400,
    "w": 604800,
    "week": 604800,
    "mo": 2592000,
    "month": 2592000,
    "y": 31536000,
    "year": 31536000,
}


def labels(names, taken=(), limit=ALIAS, spelled=SPELLED, crowded=CROWDED):
    if not ABBREVIATED:
        return {name: '"{}"'.format(titled(name)) for name in names}
    spelt = list(names) if len(names) <= crowded else [name for name in names if len(name) <= spelled]
    short = abbreviate([name for name in names if len(name) > spelled], list(taken) + spelt, limit)
    return {name: '"{}"'.format(short.get(name, titled(name))) for name in names}


def titled(name):
    return " ".join(word.capitalize() for word in name.split("_"))


def bucketed(cadence, floor=None):
    span = duration(cadence)
    wanted = span * SAMPLES if span else duration(BUCKET)
    least = (duration(floor) or 0) if floor else 0
    return next((candidate for candidate in BUCKETS if (duration(candidate) or 0) >= (wanted or 0) and (duration(candidate) or 0) >= least), BUCKETS[-1])


def recent(source, bucket=BUCKET, now="now()"):
    return ["time >= {} - INTERVAL '{}'".format(now, guarded(bucket)), "time >= (SELECT max(time) FROM {}) - INTERVAL '{}'".format(source, bucket)]


def guarded(bucket, factor=GUARD):
    count, unit = bucket.split(" ", 1)
    return "{} {}".format(int(count) * factor, unit)


def parted(selectors, keys, headers=None, width=WIDTH):
    room = max(width - (STAMPED + 3) - (keys - 1) * (KEYED + 3) - 1, CELL + 3)
    parts, current, used = [], [], 0
    for selector in selectors:
        header = (headers or {}).get(selector[1], selector[1])
        if not isinstance(header, str):
            header = selector[1] if isinstance(selector[1], str) else ""
        cost = max(len(header), CELL) + 3
        if current and used + cost > room:
            parts.append(current)
            current, used = [], 0
        current.append(selector)
        used += cost
    return parts + ([current] if current else [])


def aggregations(measure, cadence=None):
    if measure.kind == "bool":
        return [("avg", "fraction")]
    if measure.kind == "int":
        return [("last", "")]
    span, bucket = duration(cadence), duration(BUCKET)
    if span is not None and bucket is not None and span >= bucket:
        return [("avg", "")]
    return [("avg", "avg"), ("min", "min"), ("max", "max")]


def duration(period):
    matched = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([a-z]+)\s*", (period or "").lower())
    if not matched:
        return None
    unit = matched.group(2)
    unit = unit if unit in DURATIONS else unit.rstrip("s")
    return float(matched.group(1)) * DURATIONS[unit] if unit in DURATIONS else None


def abbreviate(names, taken=(), limit=ALIAS):
    used, short = {name.upper() for name in taken}, {}
    for name in names:
        form = next((candidate for candidate in _variants(name, limit) if candidate not in used),
                    _numbered(name, used, limit))
        used.add(form)
        short[name] = form
    return short


def indent(text, pad="    "):
    return [pad + line for line in text.split("\n")]


def literals(column, values, negate=True, width: int | None = 92, pad="        "):
    quoted = ["'{}'".format(str(value).replace("'", "''")) for value in values]
    wrap = float("inf") if width is None else width
    lines, current = [], ""
    for index, value in enumerate(quoted):
        separator = "," if index < len(quoted) - 1 else ""
        if current and len(pad) + len(current) + 1 + len(value) + len(separator) > wrap:
            lines.append(current)
            current = ""
        current += (" " if current else "") + value + separator
    if current:
        lines.append(current)
    if len(lines) == 1:
        return "{} {}IN ({})".format(column, "NOT " if negate else "", lines[0])
    return "\n".join(["{} {}IN (".format(column, "NOT " if negate else "")] + indent("\n".join(lines)) + [")"])


def render_statements(rendered):
    blocks, block = [], []
    for statement in [statement for statement in rendered if statement]:
        if block and not block[-1].startswith("--"):
            blocks.append(block)
            block = []
        block.append(statement if statement.startswith("--") else statement + ";")
    if block:
        blocks.append(block)
    return banner("--") + "\n\n" + "\n\n".join("\n".join(block) for block in blocks) + "\n"


def declared_measure(relation, measure, unit, period):
    return [
        ("'{}'".format(relation.path), "relation"),
        ("'{}'".format(measure.key), "measure"),
        ("'{}'".format(measure.kind), "kind"),
        ("'{}'".format(unit), "unit"),
        ("'{}'".format(period), "period")
    ]


def declared_entity(relation, column=None):
    if relation.subject is None or not relation.entities:
        return "'{}'".format(NULL)
    return "CASE WHEN {} THEN '{}' ELSE '{}' END".format(
        literals(column or relation.subject.key, relation.entities, negate=False), YES, NO)


def dimension_label(relation):
    return "/".join(key.key + (SUBJECT if key.subject else "") for key in relation.dimensions) or NULL


def grouping_keys(entity, declared_expression):
    return [entity] + ([declared_expression] if declared_expression.startswith("CASE") else [])


def script(module_name, dialect, name, summary, connect, body):
    return """
#!/usr/bin/env bash
{}

set -uo pipefail

SCHEMA_VERBOSE=${{SCHEMA_VERBOSE:-false}}
while [[ $# -gt 0 ]]; do
  case $1 in
  -v | --verbose)
    SCHEMA_VERBOSE=true
    shift
    ;;
  -h | --help | -*)
    echo "Usage: ${{0}} [-v|--verbose] [-h|--help]"
    echo "       {} {} {}"
    exit 2
    ;;
  *)
    shift
    ;;
  esac
done

ROOT_DIR="$(dirname "$(readlink -f "$0")")"
MODULE_DIR="${{ROOT_DIR}}"
while [ "${{MODULE_DIR}}" != "/" ] && [ ! -f "${{MODULE_DIR}}/.env" ]; do
  MODULE_DIR="$(dirname "${{MODULE_DIR}}")"
done

if [ ! -f "${{MODULE_DIR}}/.env" ]; then
  echo "Schema script [{}] could not find env file [.env] searching up from [${{ROOT_DIR}}]" >&2
  exit 1
fi
set -a
# shellcheck disable=SC1091
. "${{MODULE_DIR}}/.env"
set +a

if [ "${{SCHEMA_VERBOSE}}" == true ]; then
  set -x
fi

{}

{}
    """.format(banner(), dialect, name, summary, module_name, connect.strip(), body.strip()).strip() + "\n"


def describe_runner(module_name, dialect, target, connect):
    return script(module_name, dialect, "describe", "print what production actually carries", connect, """
printf '\\nSchema describe [%s] against [%s]\\n' "{1}" "${{{0}}}"
printf -- '\\n-- %s\\n\\n' "describe.sql"
SCHEMA_ECHO=false SCHEMA_ACTION=Describe SCHEMA_TARGET="${{{0}}}" \\
  query_file "${{ROOT_DIR}}/query/describe.sql"
""".format(target, module_name))


def query_runner(module_name, dialect, target, connect):
    return script(module_name, dialect, "query", "run the generated query for every declared relation", connect, """
printf '\\nSchema query [%s] against [%s]\\n\\n' "{1}" "${{{0}}}"
FAULTS=0
for SQL_FILE in "${{ROOT_DIR}}"/query/query_*.sql; do
  SCHEMA_LABEL="$(basename "${{SQL_FILE}}")" query_file "${{SQL_FILE}}" || FAULTS=$((FAULTS + 1))
done
[ "${{FAULTS}}" = 0 ]
""".format(target, module_name))


def verify_runner(module_name, dialect, target, connect):
    return script(module_name, dialect, "verify", "assert production matches the declaration", connect, """
printf '\\nSchema verify [%s] against [%s]\\n' "{1}" "${{{0}}}"
printf -- '\\n-- %s\\n\\n' "verify.sql"

FAULTS=0
while IFS= read -r STATEMENT; do
  [ -z "${{STATEMENT}}" ] && continue
  if ! RESULT="$(query "${{STATEMENT}}")"; then
    fail "${{STATEMENT}}" "${{RESULT}}"
    exit 1
  fi
  COUNT="$(printf '%s' "${{RESULT}}" | rows)"
  if [ "${{COUNT}}" != "0" ]; then
    FAULTS=$((FAULTS + COUNT))
    printf '%s\\n' "${{RESULT}}" | table
    printf '\\n'
  fi
done < <(statements "${{ROOT_DIR}}/query/verify.sql")

if [ "${{FAULTS}}" != "0" ]; then
  printf '\\nSchema verify [%s] found [%s] fault row(s)\\n' "{1}" "${{FAULTS}}" >&2
  exit 1
fi
printf '\\nSchema verify [%s] found no drift\\n' "{1}"
""".format(target, module_name))


def write_schema_dialect(module_name, schemas_dir, dialect, artifacts):
    dialect_dir = abspath(join(str(schemas_dir), dialect))
    if exists(dialect_dir):
        shutil.rmtree(dialect_dir)
    for relative_path in sorted(artifacts):
        content, executable = artifacts[relative_path]
        artifact_path = abspath(join(dialect_dir, relative_path))
        os.makedirs(dirname(artifact_path), exist_ok=True)
        with open(artifact_path, 'w') as artifact_file:
            artifact_file.write(content)
        if executable:
            os.chmod(artifact_path, 0o750)
        print("Build generate script [{}] {} schema [{}] persisted to [{}]"
              .format(module_name, dialect, relative_path, artifact_path))
    sys.stdout.flush()


def _variants(name, limit):
    words = [word for word in name.split("_") if word]
    words = words if len(words) <= limit else words[:limit - 1] + words[-1:]
    fixed = {index for index, word in enumerate(words) if any(letter.isdigit() for letter in word)}
    flexible = [word for index, word in enumerate(words) if index not in fixed]
    budget = max(limit - sum(len(words[index]) for index in fixed), len(flexible))
    for mode in ("tail", "head", "middle"):
        share = _budget(len(flexible), budget, mode) if flexible else []
        yield _assembled(words, share, fixed, {})
        for index in reversed(range(len(flexible))):
            for shift in (1, 2):
                yield _assembled(words, share, fixed, {index: shift})


def _assembled(words, share, fixed, shifts):
    parts, position = [], 0
    for index, word in enumerate(words):
        if index in fixed:
            parts.append(word)
            continue
        parts.append(_letters(word, share[position], shifts.get(position, 0)))
        position += 1
    return "".join(parts).upper()


def _letters(word, want, shift=0):
    skeleton = []
    for letter in word[:1] + "".join(letter for letter in word[1:] if letter not in VOWELS):
        if not skeleton or skeleton[-1] != letter:
            skeleton.append(letter)
    segment = "".join(skeleton)[shift:shift + want]
    return segment if len(segment) == want else word[shift:shift + want]


def _budget(count, limit, mode):
    order = {
        "head": list(range(count)),
        "middle": sorted(range(count), key=lambda index: (abs(2 * index - count + 1), index)),
        "tail": list(reversed(range(count))),
    }[mode]
    share = [1] * count
    for slack in range(limit - count):
        share[order[slack % count]] += 1
    return share


def _numbered(name, used, limit):
    base = next(iter(_variants(name, limit)))
    for number in range(2, 10):
        form = base[:limit - 1] + str(number)
        if form not in used:
            return form
    raise ValueError("cannot abbreviate [{}] without colliding".format(name))
