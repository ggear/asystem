import importlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field, fields, is_dataclass
from os.path import abspath, basename, isabs, isdir, isfile, join

from asystem.bootstrap import load_bootstrap_env_value, load_bootstrap_root

KINDS = ("float", "int", "bool", "str")
ROLES = ("state", "command", "availability")
TYPES = {
    str: "text",
    list: "an array",
    dict: "an object",
    bool: "true or false",
}


class SchemaUnreachable(Exception):
    """A backend a generate script needed to read could not be reached."""


@dataclass
class SchemaDatabaseDimension:
    key: str
    description: str = ""
    subject: bool = False
    entities: list = field(default_factory=list)


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

    def carried(self, kinds):
        return [measure for measure in self.measures if measure.persist and measure.kind in kinds]

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
    discovered: bool = False


@dataclass
class SchemaDatabaseOptions:
    time_column: str = "timestamp"
    retention: str = ""
    timezone: str = ""


@dataclass
class SchemaBrokerOptions:
    working_root: str = ""
    topic_glob_discovery: str = ""
    topic_glob_data: str = ""
    state: object = None
    command: object = None
    availability: object = None
    document: object = None


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
            "path":        "<path>",        REQUIRED  [<plugin>/<scope>], [<plugin>] is what the backend writes to,
                                                      [<plugin>] alone where there is nothing to scope, as when a
                                                      schema is discovered rather than declared
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
              "unit":        "<text>",      OPTIONAL  Unit of the value, e.g. [%] [$] [Celsius] [seconds]
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

    A [<kind>] is one of [float] [int] [bool] [str]. Which of them a backend carries is the dialect's
    call, declared as its [KINDS] and read through [carried] — influxdb3 carries all four since line
    protocol has a string field, postgres carries the numeric three since its long form pivots through
    a numeric [value] column. A measure a backend cannot carry is declared but never written by it, so
    it is reported like any other measure declared and not written.

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
        document = parse_schema_document(_run_schema_go(module_root, module_name, config, args), module_name)
    elif isdir(rust_path):
        document = parse_schema_document(_run_schema_rust(module_root, module_name, config, args), module_name)
    else:
        raise ValueError("Build generate script [{}] declares no schema reflector, expected one of [{}] [{}] [{}]"
                         .format(module_name, python_path, go_path, rust_path))
    print("Build generate script [{}] schema reflected with relations [{}] payloads [{}]"
          .format(module_name, len(document.relations), len(document.payloads)))
    sys.stdout.flush()
    return document


def parse_schema_document(text, module_name):
    try:
        parsed = json.loads(text)
    except ValueError as error:
        raise ValueError("Build generate script [{}] schema reflection emitted unparseable JSON [{}]"
                         .format(module_name, error)) from error
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
                         .format(module_name, python_path, error)) from error
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
                         .format(module_name, " ".join(command), working_dir, error.stderr.strip())) from error
    except subprocess.TimeoutExpired as error:
        raise ValueError("Build generate script [{}] schema reflection timed out [{}] in [{}]"
                         .format(module_name, " ".join(command), working_dir)) from error
    if completed.stderr.strip():
        print(completed.stderr.strip(), file=sys.stderr)
    return completed.stdout


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
        subject=_flag(module_name, scope, dimension, "subject", False),
        entities=_texts(module_name, scope, dimension, "entities"))


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
        if not relation.path or relation.path.count("/") > 1 or relation.path.startswith("/"):
            raise ValueError("Build generate script [{}] relation path must be [<plugin>/<scope>], or [<plugin>] "
                             "alone where the backend holds nothing to scope [{}]"
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
