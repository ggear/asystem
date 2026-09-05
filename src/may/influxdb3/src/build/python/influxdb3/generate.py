from asystem import *

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    write_container_bootstrap()
    write_container_healthchecks()
    write_container_backup()
    write_container_restore()

    write_schema_instance()
