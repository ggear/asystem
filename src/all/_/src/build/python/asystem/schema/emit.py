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


def write_schema_database(document, dialect="influxdb3", time_column="timestamp",
                          retention=None, entities=None, module_name=None, schemas_dir=None,
                          timezone=None):
    module_root = load_bootstrap_root()
    if module_name is None:
        module_name = basename(module_root)
    if dialect not in DIALECTS:
        raise ValueError("Build generate script [{}] unknown dialect [{}] expected one of {}"
                         .format(module_name, dialect, sorted(DIALECTS)))
    if schemas_dir is None:
        schemas_dir = join(module_root, "src/build/resources/schema")
    if document is None:
        return skip_schema_dialect(module_name, schemas_dir, dialect)
    merge_schema_entities(document, entities)
    emitter = DIALECTS[dialect]
    if timezone is None:
        timezone = load_bootstrap_env_value("TZ", "UTC", filename=ENV, module_root=module_root)
    options = SchemaDatabaseOptions(time_column=time_column, retention=retention or "",
                                    timezone=timezone)
    try:
        artifacts = emitter.artifacts(document, module_name, options)
    except SchemaUnreachable as unreachable:
        print("Build generate script [{}] could not connect to {} with error [{}]"
              .format(module_name, dialect, unreachable))
        return skip_schema_dialect(module_name, schemas_dir, dialect)
    write_schema_dialect(module_name, schemas_dir, dialect, artifacts)
    emitter.ship(document, module_name, module_root, schemas_dir, options)


def write_schema_broker(source, module_name=None, working_root=None, schemas_dir=None,
                        topic_glob_discovery=None, topic_glob_data=None,
                        schema_state=None, schema_command=None, schema_availability=None, document=None):
    module_root = load_bootstrap_root()
    if module_name is None:
        module_name = basename(module_root)
    if working_root is None:
        working_root = join(module_root, "src/main/resources/image")
    if schemas_dir is None:
        schemas_dir = join(module_root, "src/build/resources/schema")
    if source is None:
        return skip_schema_dialect(module_name, schemas_dir, vernemq.DIALECT)
    options = SchemaBrokerOptions(
        working_root=str(working_root),
        topic_glob_discovery=topic_glob_discovery or "",
        topic_glob_data=topic_glob_data or "",
        state=schema_state, command=schema_command, availability=schema_availability, document=document)
    empty = not source.payloads if isinstance(source, SchemaDocument) else len(source) == 0
    try:
        artifacts = {} if empty else vernemq.artifacts(source, module_name, options)
    except SchemaUnreachable as unreachable:
        print("Build generate script [{}] could not connect to {} with error [{}]"
              .format(module_name, vernemq.DIALECT, unreachable))
        return skip_schema_dialect(module_name, schemas_dir, vernemq.DIALECT)
    write_schema_dialect(module_name, schemas_dir, vernemq.DIALECT, artifacts)
    if not empty:
        vernemq.ship(source, module_name, module_root, schemas_dir, options)


def skip_schema_dialect(module_name, schemas_dir, dialect):
    dialect_dir = abspath(join(str(schemas_dir), dialect))
    print("Build generate script [{}] {} schema not generated, keeping the existing artifacts in [{}]"
          .format(module_name, dialect, dialect_dir))
    sys.stdout.flush()
    return None


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
