import os
import shutil
import sys
from os.path import abspath, basename, dirname, exists, join

from asystem.bootstrap import load_bootstrap_env_value, load_bootstrap_root
from asystem.schema.dialects import influxdb3, postgres, vernemq
from asystem.schema.document import (
    SchemaBrokerOptions,
    SchemaDatabaseOptions,
    SchemaDocument,
    SchemaUnreachable,
    merge_schema_entities,
)

ENV = ".env"

DIALECTS = {
    influxdb3.DIALECT: influxdb3,
    postgres.DIALECT: postgres,
}


def write_schema_database(document, module_name=None, schemas_dir=None,
                          database_dialect="influxdb3", database_time_column="timestamp", database_retention=None,
                          database_timezone=None, database_entities=None, database_applier=False,
                          database_rename_measures=None, database_drop_measures=None,
                          database_archive_measures=None):
    module_root = load_bootstrap_root()
    if module_name is None:
        module_name = basename(module_root)
    if database_dialect not in DIALECTS:
        raise ValueError("Build generate script [{}] unknown dialect [{}] expected one of {}"
                         .format(module_name, database_dialect, sorted(DIALECTS)))
    if schemas_dir is None:
        schemas_dir = join(module_root, "src/build/resources/schema")
    if document is None:
        return _skip_schema_dialect(module_name, schemas_dir, database_dialect)
    merge_schema_entities(document, database_entities)
    emitter = DIALECTS[database_dialect]
    if database_timezone is None:
        database_timezone = load_bootstrap_env_value("TZ", "UTC", filename=ENV, module_root=module_root)
    rename = _rename_measures(database_rename_measures)
    drop = _retired_measures(database_drop_measures)
    archive = _retired_measures(database_archive_measures)
    _validate_retired(document, module_name, rename, drop, archive)
    options = SchemaDatabaseOptions(time_column=database_time_column, retention=database_retention or "",
                                    timezone=database_timezone, applier=database_applier,
                                    rename=rename, drop=drop, archive=archive)
    try:
        artifacts = emitter.artifacts(document, module_name, options)
    except SchemaUnreachable as unreachable:
        print("Build generate script [{}] could not connect to {} with error [{}]"
              .format(module_name, database_dialect, unreachable))
        return _skip_schema_dialect(module_name, schemas_dir, database_dialect)
    _write_schema_dialect(module_name, schemas_dir, database_dialect, artifacts)
    emitter.ship(document, module_name, module_root, schemas_dir, options)


def _rename_measures(rename):
    expanded = {}
    for old, new in (rename or {}).items():
        expanded[old] = new or ""
        expanded["{}_trend".format(old)] = "{}_trend".format(new) if new else ""
    return expanded


def _retired_measures(retired):
    expanded = []
    for key in retired or ():
        expanded.extend((key, "{}_trend".format(key)))
    return sorted(set(expanded))


def _validate_retired(document, module_name, rename, drop, archive):
    verbs = (("renamed", set(rename)), ("dropped", set(drop)), ("archived", set(archive)))
    for index, (verb, keys) in enumerate(verbs):
        for other, others in verbs[index + 1:]:
            both = sorted(keys & others)
            if both:
                raise ValueError("Build generate script [{}] measures {} are declared as both {} and {}, "
                                 "a retired measure is retired exactly once"
                                 .format(module_name, both, verb, other))
    declared = {measure.key for relation in document.relations for measure in relation.measures}
    live = sorted((set(rename) | set(drop) | set(archive)) & declared)
    if live:
        raise ValueError("Build generate script [{}] measures {} are declared as renamed, dropped or archived but "
                         "the service still declares them, retire the declaration first".format(module_name, live))


def write_schema_broker(source, module_name=None, schemas_dir=None,
                        broker_working_dir=None, broker_topic_glob_discovery=None,
                        broker_topic_glob_data=None, broker_state=None, broker_command=None,
                        broker_availability=None, broker_document=None, broker_entities=None):
    module_root = load_bootstrap_root()
    if module_name is None:
        module_name = basename(module_root)
    if broker_working_dir is None:
        broker_working_dir = join(module_root, "src/main/resources/image")
    if schemas_dir is None:
        schemas_dir = join(module_root, "src/build/resources/schema")
    if source is None:
        return _skip_schema_dialect(module_name, schemas_dir, vernemq.DIALECT)
    options = SchemaBrokerOptions(
        working_dir=str(broker_working_dir),
        topic_glob_discovery=broker_topic_glob_discovery or "",
        topic_glob_data=broker_topic_glob_data or "",
        state=broker_state, command=broker_command,
        availability=broker_availability, document=broker_document,
        entities=broker_entities)
    declared = broker_document is not None and bool(getattr(broker_document, "topics", None))
    empty = (not source.payloads if isinstance(source, SchemaDocument)
             else len(source) == 0 and not declared)
    try:
        artifacts = {} if empty else vernemq.artifacts(source, module_name, options)
    except SchemaUnreachable as unreachable:
        print("Build generate script [{}] could not connect to {} with error [{}]"
              .format(module_name, vernemq.DIALECT, unreachable))
        return _skip_schema_dialect(module_name, schemas_dir, vernemq.DIALECT)
    _write_schema_dialect(module_name, schemas_dir, vernemq.DIALECT, artifacts)
    vernemq.ship(source, module_name, module_root, schemas_dir, options)


def _skip_schema_dialect(module_name, schemas_dir, dialect):
    dialect_dir = abspath(join(str(schemas_dir), dialect))
    print("Build generate script [{}] {} schema not generated, keeping the existing artifacts in [{}]"
          .format(module_name, dialect, dialect_dir))
    sys.stdout.flush()
    return None


def _write_schema_dialect(module_name, schemas_dir, dialect, artifacts):
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
