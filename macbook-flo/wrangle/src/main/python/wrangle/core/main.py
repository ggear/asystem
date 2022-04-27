import glob
import importlib
import os
import sys

from wrangle.core.plugin import library


def main(arguments=[]):
    module_count = 0
    module_errored_count = 0
    for module_path in glob.glob("{}/plugin/*/*.py".format(os.path.dirname(os.path.realpath(__file__)))):
        if not module_path.endswith("__init__.py"):
            module_name = os.path.basename(os.path.dirname(module_path))
            module = getattr(importlib.import_module("wrangle.core.plugin.{}".format(module_name)), module_name.title())()
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
                module.print_log("Module threw unexpected exception:", exception)
                module_errored = True
            if module_errored:
                module_errored_count += 1
    return module_count != 0 and module_count > module_errored_count


if __name__ == "__main__":
    sys.exit(0 if main(sys.argv) else 1)
