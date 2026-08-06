import fnmatch
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field, fields, is_dataclass
from os.path import *

KINDS = ("float", "int", "bool", "str")
ROLES = ("state", "command", "availability")
DIALECTS = ("influxdb3", "postgres")


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
    if module_root is None:
        module_root = abspath(join(dirname(realpath(realpath(sys.argv[0]))), "../../../.."))
    module_name = basename(module_root)
    if config is not None and not isabs(config):
        config = abspath(join(module_root, config))
    python_path = join(module_root, "src/main/python", module_name, "plugin/schema.py")
    go_path = join(module_root, "src/main/go", module_name, "tools/schema")
    rust_path = join(module_root, "src/main/rust", module_name, "src/bin/schema.rs")
    if isfile(python_path):
        document = _load_schema_python(module_root, module_name, python_path, config)
    elif isdir(go_path):
        document = _parse_document(_run_schema_go(module_root, module_name, config, args), module_name)
    elif isfile(rust_path):
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
    for path, values in entities.items():
        if path not in relations:
            raise ValueError("Build generate script [{}] entities supplied for undeclared relation [{}]"
                             .format(document.module, path))
        relation = relations[path]
        values = [str(value) for value in values]
        if relation.entities and sorted(relation.entities) != sorted(values):
            raise ValueError(
                "Build generate script [{}] relation [{}] declares entities {} but the emitter was passed {}: "
                "the code declaration wins, so make them agree or drop the override"
                .format(document.module, path, sorted(relation.entities), sorted(values)))
        relation.entities = values
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
    env = _toolchain_env(module_root)
    go_version = env.get("ASYSTEM_GO_VERSION", "")
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
    env = _toolchain_env(module_root)
    cargo_home = join(os.environ["HOME"], ".rust/versions/asystem")
    cargo_binary = join(cargo_home, "bin/cargo")
    if not isfile(cargo_binary):
        raise ValueError("Build generate script [{}] cargo binary not found [{}]".format(module_name, cargo_binary))
    command = [cargo_binary, "run", "--quiet", "--bin", "schema", "--"]
    if config is not None:
        command += ["--sensors", config]
    command += list(args or [])
    return _run(module_name, command, join(module_root, "src/main/rust", module_name), {
        "CARGO_HOME": cargo_home,
        "RUSTUP_HOME": cargo_home,
        "CARGO_TARGET_DIR": join(module_root, "target/rust"),
        "RUSTUP_TOOLCHAIN": env.get("ASYSTEM_RUST_VERSION", ""),
        "PATH": join(cargo_home, "bin") + os.pathsep + os.environ.get("PATH", ""),
    })


def _run(module_name, command, working_dir, overrides):
    env = dict(os.environ)
    env.update({key: value for key, value in overrides.items() if value})
    try:
        completed = subprocess.run(command, cwd=working_dir, env=env, check=True,
                                   capture_output=True, text=True, timeout=120)
    except subprocess.CalledProcessError as error:
        raise ValueError("Build generate script [{}] schema reflection failed [{}] in [{}] with [{}]"
                         .format(module_name, " ".join(command), working_dir, error.stderr.strip()))
    except subprocess.TimeoutExpired:
        raise ValueError("Build generate script [{}] schema reflection timed out [{}] in [{}]"
                         .format(module_name, " ".join(command), working_dir))
    if completed.stderr.strip():
        print(completed.stderr.strip(), file=sys.stderr)
    return completed.stdout


def _toolchain_env(module_root):
    env = {}
    env_path = join(module_root, ".env")
    if not isfile(env_path):
        return env
    for line in open(env_path, 'r'):
        line = line.replace("export ", "").rstrip()
        if "=" not in line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        env[key] = value
    return env


def _parse_document(text, module_name):
    """Parse the JSON a Go or Rust schema reflector prints on stdout.

    A schema document, as the reflector prints it:

    {
        "module":      "<name>",            OPTIONAL  Owning module, defaults to the module directory name
        "database":    {                    OPTIONAL  What the service writes to a database backend
          "relations":   [{                 OPTIONAL  One per distinct row shape written
            "path":        "<path>",        REQUIRED  [<plugin>/<scope>], [<plugin>] is the measurement or table
            "description": "<text>",        OPTIONAL  What the relation holds
            "cadence":     "<duration>",    OPTIONAL  The service's real publish period
            "entities":    ["<entity>"],    OPTIONAL  Values the subject takes, generate.py may fill them instead
            "dimensions":  [{               OPTIONAL  What identifies a row
              "key":         "<name>",      REQUIRED  Tag name in influxdb3, the postgres columns are fixed
              "description": "<text>",      OPTIONAL  What the dimension distinguishes
              "subject":     <true|false>   OPTIONAL  The entity axis, at most one per relation, defaults to false
            }],
            "measures":    [{               OPTIONAL  What a row carries
              "key":         "<name>",      REQUIRED  Field name in influxdb3, [type] value in postgres
              "kind":        "<kind>",      REQUIRED  Value type
              "unit":        "<text>",      OPTIONAL  Unit of the value, e.g. [%] [$] [celsius] [seconds]
              "description": "<text>",      OPTIONAL  What the measure records
              "persist":     <true|false>,  OPTIONAL  Declared but never written when false, defaults to true
              "period":      "<duration>"   OPTIONAL  Span the value covers, defaults to the relation cadence
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
    It is carried verbatim into the artefacts, never parsed.

    A [<member>], nesting arbitrarily deep through its own [members]:

    {
        "key":         "<name>",            OPTIONAL  Member name, empty for the root of a bare payload
        "kind":        "<kind>",            OPTIONAL  Scalar type, ignored when [members] or [enum] is set
        "enum":        ["<option>"],        OPTIONAL  Renders as [<a|b|c>] in place of the kind placeholder
        "members":     [<member>]           OPTIONAL  Nested members, which make this an object
    }
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
        relations=[_parse_relation(module_name, relation)
                   for relation in _mappings(module_name, "database", database, "relations")],
        payloads=[_parse_payload(module_name, payload)
                  for payload in _mappings(module_name, "broker", broker, "payloads")])
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
        dimensions=[_parse_dimension(module_name, scope, dimension)
                    for dimension in _mappings(module_name, scope, relation, "dimensions")],
        measures=[_parse_measure(module_name, scope, measure)
                  for measure in _mappings(module_name, scope, relation, "measures")])


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
        members=[_parse_member(module_name, scope, nested)
                 for nested in _mappings(module_name, scope, member, "members")])


def _scope(scope, noun, mapping, key="key"):
    return "{}{} [{}]".format(scope + " " if scope else "", noun,
                              mapping.get(key, "") if isinstance(mapping, dict) else "")


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
    value = mapping.get(key)
    value = default if value is None else value
    if value is None:
        raise ValueError("Build generate script [{}] schema reflection {} requires key [{}]"
                         .format(module_name, scope, key))
    if not isinstance(value, str):
        raise ValueError("Build generate script [{}] schema reflection {} emitted key [{}] as [{}] expected text"
                         .format(module_name, scope, key, type(value).__name__))
    return value


def _texts(module_name, scope, mapping, key):
    values = mapping.get(key)
    if values is None:
        return []
    if not isinstance(values, list):
        raise ValueError("Build generate script [{}] schema reflection {} emitted key [{}] as [{}] expected an array"
                         .format(module_name, scope, key, type(values).__name__))
    for value in values:
        if not isinstance(value, str):
            raise ValueError("Build generate script [{}] schema reflection {} emitted key [{}] element [{}] as [{}] "
                             "expected text".format(module_name, scope, key, value, type(value).__name__))
    return list(values)


def _flag(module_name, scope, mapping, key, default):
    value = mapping.get(key)
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ValueError("Build generate script [{}] schema reflection {} emitted key [{}] as [{}] expected "
                         "true or false".format(module_name, scope, key, type(value).__name__))
    return value


def _mapping(module_name, scope, mapping, key):
    value = mapping.get(key)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("Build generate script [{}] schema reflection {} emitted key [{}] as [{}] expected an object"
                         .format(module_name, scope, key, type(value).__name__))
    return value


def _mappings(module_name, scope, mapping, key):
    values = mapping.get(key)
    if values is None:
        return []
    if not isinstance(values, list):
        raise ValueError("Build generate script [{}] schema reflection {} emitted key [{}] as [{}] expected an array"
                         .format(module_name, scope, key, type(values).__name__))
    return values


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


def write_schema_database(document, dialect="influxdb3", time_column="timestamp", retention=None,
                          entities=None, module_name=None, schemas_dir=None,
                          describe=True, queries=True, verify=True):
    if dialect not in DIALECTS:
        raise ValueError("Build generate script [{}] unknown dialect [{}] expected one of {}"
                         .format(document.module, dialect, list(DIALECTS)))
    module_root = abspath(join(dirname(realpath(realpath(sys.argv[0]))), "../../../.."))
    if module_name is None:
        module_name = basename(module_root)
    if schemas_dir is None:
        schemas_dir = join(module_root, "src/build/resources/schema")
    merge_schema_entities(document, entities)
    tables = {}
    if dialect == "influxdb3":
        if time_column != "timestamp" or retention is not None:
            raise ValueError("Build generate script [{}] time_column and retention are postgres only, "
                             "the influxdb3 dialect must never be wired to them".format(module_name))
        artifacts = _artifacts_influxdb(document, module_name, dialect,
                                        describe, queries, verify)
    else:
        if time_column not in ("date", "timestamp"):
            raise ValueError("Build generate script [{}] unknown time_column [{}] expected date or timestamp"
                             .format(module_name, time_column))
        artifacts, tables = _artifacts_postgres(document, module_name, dialect, time_column, retention,
                                                describe, queries, verify)
    write_schema_dialect(module_name, schemas_dir, dialect, artifacts)
    if dialect == "postgres":
        _ship_postgres(module_name, module_root, schemas_dir, dialect, tables, time_column)


def write_schema_broker(metadata_df, module_name=None, working_root=None, schemas_dir=None,
                        topic_glob_discovery=None, topic_glob_data=None,
                        schema_state=None, schema_command=None, schema_availability=None,
                        describe=True, queries=True, verify=True, discover=False, document=None):
    from asystem import schema_vernemq
    if len(metadata_df) == 0:
        return
    module_root = abspath(join(dirname(realpath(realpath(sys.argv[0]))), "../../../.."))
    if module_name is None:
        module_name = basename(module_root)
    if working_root is None:
        working_root = join(module_root, "src/main/resources/image")
    if schemas_dir is None:
        schemas_dir = join(module_root, "src/build/resources/schema")
    dialect = schema_vernemq.DIALECT
    _validate_topics(metadata_df, module_name, topic_glob_discovery, topic_glob_data)
    topics = _broker_topics(metadata_df, module_name)
    specs = _broker_specs(module_name, document, schema_state, schema_command, schema_availability)
    if topics:
        artifacts = _artifacts_vernemq(module_name, dialect, topic_glob_discovery, topic_glob_data,
                                       topics, specs, document, describe, queries, verify, discover)
        write_schema_dialect(module_name, schemas_dir, dialect, artifacts)
    _ship_vernemq(metadata_df, module_name, working_root, dialect,
                  topic_glob_discovery, topic_glob_data)


def _validate_topics(metadata_df, module_name, topic_glob_discovery, topic_glob_data):
    for topic_glob, topic_glob_name, topic_glob_column in (
            (topic_glob_discovery, "topic_glob_discovery", "discovery_topic"),
            (topic_glob_data, "topic_glob_data", "state_topic")):
        if topic_glob is None:
            continue
        unmatched = [topic for topic in _column_topics(metadata_df, topic_glob_column)
                     if not _topic_glob_match(topic_glob, topic)]
        if unmatched:
            raise ValueError(
                "Build generate script [{}] {} [{}] does not match entity_metadata.xlsx {} topic(s) {}: "
                "update the glob or the spreadsheet so they agree"
                .format(module_name, topic_glob_name, topic_glob, topic_glob_column, unmatched))


def _topic_glob_match(topic_glob, topic):
    glob_levels = topic_glob.split("/")
    topic_levels = topic.split("/")
    for index, glob_level in enumerate(glob_levels):
        if glob_level == "#":
            return True
        if index >= len(topic_levels):
            return False
        if glob_level == "+":
            continue
        if not fnmatch.fnmatchcase(topic_levels[index], re.sub(r"\$\{[^}]+}", "*", glob_level)):
            return False
    return len(glob_levels) == len(topic_levels)


def _column_topics(metadata_df, column):
    if column not in metadata_df.columns:
        return []
    return sorted({topic.strip() for topic in metadata_df[column].dropna().unique() if topic.strip()})


def _broker_topics(metadata_df, module_name):
    from asystem import schema_vernemq
    topics = {column: _column_topics(metadata_df, column) for column in schema_vernemq.TOPIC_COLUMNS}
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


def _broker_specs(module_name, document, schema_state, schema_command, schema_availability):
    from asystem import schema_vernemq
    specs = {column: spec for column, spec in (("state_topic", schema_state),
                                               ("command_topic", schema_command),
                                               ("availability_topic", schema_availability))
             if spec is not None}
    if document is not None:
        for column, role in schema_vernemq.ROLE_COLUMNS.items():
            if column in specs and any(payload.role == role for payload in document.payloads):
                raise ValueError(
                    "Build generate script [{}] role [{}] is declared in code and also passed as a literal [{}]: "
                    "supply one or the other, never both".format(module_name, role, column))
    specs["discovery_topic"] = schema_vernemq.DISCOVERY_PAYLOAD
    return specs


def _artifacts_vernemq(module_name, dialect, topic_glob_discovery, topic_glob_data,
                       topics, specs, document, describe, queries, verify, discover):
    from asystem import schema_vernemq
    globs = [glob for glob in (topic_glob_discovery, topic_glob_data) if glob]
    artifacts = {}
    for column, column_topics in topics.items():
        role = schema_vernemq.ROLE_COLUMNS.get(column, "") if document is not None else ""
        for topic in column_topics:
            artifacts["model/{}".format(topic)] = (
                schema_vernemq.leaf(topic, specs.get(column, ""), document, role), False)
    if describe:
        artifacts["describe.sh"] = (schema_vernemq.describe_script(module_name, dialect, globs), True)
    if queries:
        artifacts["query.sh"] = (schema_vernemq.query_script(module_name, dialect), True)
    if verify:
        artifacts["verify.sh"] = (
            schema_vernemq.verify_script(module_name, dialect, globs, sorted(topics.get("command_topic", []))), True)
    if discover:
        artifacts["discover.sh"] = (schema_vernemq.discover_script(module_name, dialect, globs), True)
    return artifacts


def _ship_vernemq(metadata_df, module_name, working_root, dialect, topic_glob_discovery, topic_glob_data):
    from asystem import schema_vernemq
    working_dir = join(str(working_root), dialect)
    if exists(working_dir):
        shutil.rmtree(working_dir)
    for _, row in metadata_df.iterrows():
        discovery_dir = abspath(join(working_dir, str(row["discovery_topic"])))
        os.makedirs(discovery_dir)
        discovery_path = abspath(join(discovery_dir, str(row["unique_id"]) + ".json"))
        with open(discovery_path, 'a') as discovery_file:
            discovery_file.write(schema_vernemq.discovery(row))
        print("Build generate script [{}] entity metadata [sensor.{}] persisted to [{}]"
              .format(module_name, row["unique_id"], discovery_path))
    publish_path = abspath(join(str(working_root), dialect + ".sh"))
    with open(publish_path, 'w') as publish_file:
        publish_file.write(schema_vernemq.publish_script(module_name, topic_glob_discovery, topic_glob_data))
    os.chmod(publish_path, 0o750)
    print("Build generate script [{}] entity metadata publish script persisted to [{}]"
          .format(module_name, publish_path))


def _artifacts_postgres(document, module_name, dialect, time_column, retention,
                        describe, queries, verify):
    from asystem import schema_postgres
    tables = {relation.path: relation.plugin for relation in document.relations}
    artifacts = {}
    by_table = {}
    for relation in document.relations:
        by_table.setdefault(tables[relation.path], []).append(relation)
    for table, relations in by_table.items():
        artifacts["model/{}.sql".format(table)] = (
            schema_postgres.leaf(relations, table, time_column, retention), False)
    if describe:
        artifacts["query/describe.sql"] = (
            schema_postgres.describe(document, tables), False)
        artifacts["describe.sh"] = (schema_postgres.describe_script(module_name, dialect), True)
    if queries:
        for table, relations in by_table.items():
            artifacts["query/query_{}.sql".format(table)] = (
                schema_postgres.queries(relations, table, time_column), False)
        artifacts["query.sh"] = (schema_postgres.query_script(module_name, dialect), True)
    if verify:
        artifacts["query/verify.sql"] = (schema_postgres.verify(document, tables), False)
        artifacts["verify.sh"] = (schema_postgres.verify_script(module_name, dialect), True)
    return artifacts, tables


def _ship_postgres(module_name, module_root, schemas_dir, dialect, tables, time_column):
    from asystem import schema_postgres
    image_dir = abspath(join(module_root, "src/main/resources/image/database"))
    if exists(image_dir):
        shutil.rmtree(image_dir)
    os.makedirs(image_dir, exist_ok=True)
    for table in sorted(set(tables.values())):
        source_path = abspath(join(schemas_dir, dialect, "model", "{}.sql".format(table)))
        target_path = join(image_dir, "{}.sql".format(table))
        shutil.copyfile(source_path, target_path)
        columns_path = join(image_dir, "{}.json".format(table))
        with open(columns_path, 'w') as columns_file:
            columns_file.write(json.dumps(schema_postgres.columns(table, time_column), indent=2) + "\n")
        print("Build generate script [{}] database table [{}] shipped to [{}] and [{}]"
              .format(module_name, table, target_path, columns_path))
    applier_path = abspath(join(module_root, "src/main/resources/image/database.sh"))
    with open(applier_path, 'w') as applier_file:
        applier_file.write(schema_postgres.applier_script(module_name))
    os.chmod(applier_path, 0o750)
    print("Build generate script [{}] database applier persisted to [{}]".format(module_name, applier_path))


def _artifacts_influxdb(document, module_name, dialect, describe, queries, verify):
    from asystem import schema_influxdb
    artifacts = {}
    scopes = {}
    for relation in document.relations:
        if not relation.persisted:
            continue
        if relation.scope in scopes:
            raise ValueError(
                "Build generate script [{}] relations [{}] and [{}] share the scope [{}] so both would write "
                "the same leaf, rename one scope".format(module_name, scopes[relation.scope], relation.path,
                                                         relation.scope))
        scopes[relation.scope] = relation.path
        artifacts["model/{}.lp".format(relation.scope)] = (schema_influxdb.leaf(relation), False)
    if describe:
        artifacts["query/describe.sql"] = (schema_influxdb.describe(document), False)
        artifacts["describe.sh"] = (schema_influxdb.describe_script(module_name, dialect), True)
    if queries:
        for measurement in schema_influxdb.measurements(document):
            artifacts["query/query_{}.sql".format(measurement)] = (
                schema_influxdb.queries(document, schema_influxdb.measured(document, measurement)), False)
        artifacts["query.sh"] = (schema_influxdb.query_script(module_name, dialect), True)
    if verify:
        artifacts["query/verify.sql"] = (schema_influxdb.verify(document), False)
        artifacts["verify.sh"] = (schema_influxdb.verify_script(module_name, dialect), True)
    return artifacts


def banner(prefix="#"):
    rule = prefix * (80 // len(prefix))
    return "{0}\n{1} WARNING: This file is written by the build process, any manual edits will be lost!\n{0}".format(
        rule, prefix)


def vocabulary(relation, prefix="#", width=110):
    lines = ["{} {} [{}]".format(prefix, relation.path, relation.description)]
    if relation.cadence:
        lines.append("{}   cadence {}".format(prefix, relation.cadence))
    for dimension in relation.dimensions:
        lines.append("{}   tag {}{} [{}]".format(
            prefix, dimension.key, SUBJECT if dimension.subject else "", dimension.description))
    if relation.subject is not None:
        lines += _entities(relation.entities, prefix, width)
    for measure in relation.measures:
        lines.append("{}   field {} {} {} [{}]{}".format(
            prefix, measure.key, UNITS.get(measure.unit, measure.unit) or NULL,
            measure.period or relation.cadence or NULL,
            measure.description, "" if measure.persist else " (not persisted)"))
    return lines


def _entities(entities, prefix, width):
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


def select(selectors, source, predicates=(), group_by=(), having=(), order_by=(), limit=None,
           distinct_on=(), leading=""):
    width = max([len(expression) for expression, alias in selectors
                 if alias and "\n" not in expression] or [0])
    rendered = []
    for expression, alias in selectors:
        if "\n" in expression:
            wrapped = indent(expression)
            rendered.append("\n".join(wrapped[:-1] + ["{} AS {}".format(wrapped[-1], alias)] if alias else wrapped))
        else:
            rendered.append("    {} AS {}".format(expression.ljust(width), alias) if alias
                            else "    {}".format(expression))
    lines = [leading + "SELECT" + (" DISTINCT ON ({})".format(", ".join(distinct_on)) if distinct_on else "")]
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

DESCRIBE_RELATIONS = ("relation", "dimension", "cadence", "measures", "persisted",
                      "declared", "observed", "rows", "oldest", "newest")
DESCRIBE_MEASURES = ("relation", "measure", "kind", "unit", "period")
DESCRIBE_ENTITIES = ("relation", "dimension", "entity", "declared", "rows", "oldest", "newest")


def values(rows, alias, columns):
    lines = ["(VALUES"]
    for index, row in enumerate(rows):
        cells = ", ".join("'{}'".format(str(cell).replace("'", "''")) for cell in row)
        lines += indent("({}){}".format(cells, "," if index < len(rows) - 1 else ""))
    lines.append(") AS {}({})".format(alias, ", ".join(columns)))
    return "\n".join(lines)


def outer(declared, observed, keys, alias="observed"):
    predicates = " AND ".join("declared.{0} = {1}.{0}".format(key, alias) for key in keys)
    return "{}\nFULL OUTER JOIN (\n{}\n) AS {} ON {}".format(
        declared, "\n".join(indent(observed)), alias, predicates)


def measures(dialect_keys, alias="observed"):
    selectors = [("coalesce(declared.relation, '{}')".format(NULL), "relation")]
    selectors += [("coalesce(declared.{0}, {1}.{0})".format(key, alias) if key in dialect_keys
                   else "coalesce(declared.{}, '{}')".format(key, NULL), key)
                  for key in DESCRIBE_MEASURES[1:]]
    selectors.append(("CASE WHEN {}.{} IS NULL THEN '{}' ELSE '{}' END".format(
        alias, dialect_keys[0], NO, YES), "observed"))
    return selectors


def switch(column, values, default):
    if len(values) == 1:
        return "'{}'".format(next(iter(values)))
    branches = ["WHEN {} THEN '{}'".format(literals(column, sorted(values[label]), negate=False), label)
                for label in sorted(values)]
    return "\n".join(["CASE"] + [line for branch in branches for line in indent(branch)] +
                     ["    ELSE '{}'".format(default), "END"])


def indent(text, pad="    "):
    return [pad + line for line in text.split("\n")]


def literals(column, values, negate=True, width=92, pad="        "):
    quoted = ["'{}'".format(value) for value in values]
    lines, current = [], ""
    for index, value in enumerate(quoted):
        separator = "," if index < len(quoted) - 1 else ""
        if current and len(pad) + len(current) + 1 + len(value) + len(separator) > width:
            lines.append(current)
            current = ""
        current += (" " if current else "") + value + separator
    if current:
        lines.append(current)
    if len(lines) == 1:
        return "{} {}IN ({})".format(column, "NOT " if negate else "", lines[0])
    return "\n".join(["{} {}IN (".format(column, "NOT " if negate else "")] + indent("\n".join(lines)) + [")"])


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
MODULE_DIR="$(readlink -f "${{ROOT_DIR}}/../../../../..")"

if [ ! -f "${{MODULE_DIR}}/.env" ]; then
  echo "Schema script [{}] could not find env file [${{MODULE_DIR}}/.env]" >&2
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
