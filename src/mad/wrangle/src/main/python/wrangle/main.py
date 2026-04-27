import glob
import importlib
import sys
from os.path import *

from wrangle.plugin import library


def main():
    module_count = 0
    module_errored_count = 0
    for module_path in glob.glob("{}/plugin/*/*.py".format(dirname(realpath(__file__)))):
        if not module_path.endswith("__init__.py"):
            module_name = basename(dirname(module_path))
            module = getattr(importlib.import_module("wrangle.plugin.{}".format(module_name)), module_name.title())()
            module_count += 1
            module_errored = False
            try:
                module.run()
                counters = module.get_counters()
                for source in counters:
                    for action in counters[source]:
                        if action == library.CTR_ACT_ERRORED and counters[source][action] > 0:
                            module_errored = True
            except Exception as exception:
                module.print_log("Module threw unexpected exception", exception=exception)
                module_errored = True
            if module_errored:
                module_errored_count += 1
    return module_count != 0 and module_count > module_errored_count


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
