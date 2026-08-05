from asystem import *

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    write_container_healthchecks()

    # Build database schema
    write_schema_database(load_schema_document(), dialect="postgres", time_column="date", discover=True)
