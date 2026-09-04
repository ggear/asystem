from asystem import *

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    write_container_healthchecks()
    write_container_backup()

    # Build database schema
    write_schema_database(load_schema_document(), database_dialect="postgres", database_time_column="date")
