import os
import shutil
import sys
from os.path import abspath, basename, dirname, exists, join

from asystem.bootstrap import load_bootstrap_root
from asystem.schema.dialects import influxdb3, postgres, vernemq
from asystem.schema.document import SchemaBrokerOptions, SchemaDatabaseOptions, merge_schema_entities

DIALECTS = {
    influxdb3.DIALECT: influxdb3,
    postgres.DIALECT: postgres,
}


def write_schema_database(document, dialect="influxdb3", time_column="timestamp",
                          retention=None, entities=None, module_name=None, schemas_dir=None):
    if dialect not in DIALECTS:
        raise ValueError("Build generate script [{}] unknown dialect [{}] expected one of {}"
                         .format(document.module, dialect, sorted(DIALECTS)))
    module_root = load_bootstrap_root()
    if module_name is None:
        module_name = basename(module_root)
    if schemas_dir is None:
        schemas_dir = join(module_root, "src/build/resources/schema")
    merge_schema_entities(document, entities)
    emitter = DIALECTS[dialect]
    options = SchemaDatabaseOptions(time_column=time_column, retention=retention or "")
    write_schema_dialect(module_name, schemas_dir, dialect, emitter.artifacts(document, module_name, options))
    emitter.ship(document, module_name, module_root, schemas_dir, options)


def write_schema_broker(metadata_df, module_name=None, working_root=None, schemas_dir=None,
                        topic_glob_discovery=None, topic_glob_data=None,
                        schema_state=None, schema_command=None, schema_availability=None, document=None):
    module_root = load_bootstrap_root()
    if module_name is None:
        module_name = basename(module_root)
    if working_root is None:
        working_root = join(module_root, "src/main/resources/image")
    if schemas_dir is None:
        schemas_dir = join(module_root, "src/build/resources/schema")
    options = SchemaBrokerOptions(
        working_root=str(working_root),
        topic_glob_discovery=topic_glob_discovery or "",
        topic_glob_data=topic_glob_data or "",
        state=schema_state, command=schema_command, availability=schema_availability, document=document)
    empty = len(metadata_df) == 0
    artifacts = {} if empty else vernemq.artifacts(metadata_df, module_name, options)
    write_schema_dialect(module_name, schemas_dir, vernemq.DIALECT, artifacts)
    if not empty:
        vernemq.ship(metadata_df, module_name, module_root, schemas_dir, options)


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
