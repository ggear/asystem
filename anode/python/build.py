from pybuilder import bootstrap
from pybuilder.core import Author, init, use_plugin

use_plugin("python.core")
use_plugin("python.unittest")

# use_plugin("python.coverage")

use_plugin("copy_resources")
use_plugin('filter_resources')

use_plugin("python.distutils")

use_plugin("python.install_dependencies")

default_task = ["publish"]

name = "anode"
summary = "ASystem Anode"
description = """ASystem Anode"""

authors = [Author("Graham Gear", "some@email.com")]
license = "Apache License"
version = "1.0.dev"


@init
def initialize(project):
    project.build_depends_on('mockito')
    project.set_property("coverage_threshold_warn", 50)

    with open("requirements.txt", "r") as requirements:
        for requirement in requirements.readlines():
            requirement_tokens = requirement.split("==")
            project.depends_on(requirement_tokens[0].strip(), requirement_tokens[1].strip() if len(requirement_tokens) > 1 else None)

    project.set_property("distutils_readme_description", True)
    project.set_property("distutils_description_overwrite", True)
    project.set_property("distutils_console_scripts", ["anode=anode.anode:main"])

    # project.set_property("copy_resources_target", "$dir_dist/anode")
    # project.set_property("copy_resources_glob", ["src/main/python/anode/web/**", "src/main/python/anode/avro/**", "src/main/python/anode/*.properties"])
    # project.get_property("filter_resources_glob").append("**/anode/__init__.py")
    # project.get_property("filter_resources_glob").append("**/anode/application.properties")
    # project.get_property("filter_resources_glob").append("**/anode/avro/model.properties")
    # project.include_file("anode", "avro/**")
    # project.include_file("anode", "application.properties")
    # project.install_file("avro/model.properties","avro/model.properties")
    # project.install_file("application.properties", "anode/application.properties")
