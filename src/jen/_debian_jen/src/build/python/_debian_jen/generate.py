import urllib3

from asystem import *

urllib3.disable_warnings()

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    write_container_volumes()
