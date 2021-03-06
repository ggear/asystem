import os

import setuptools
from pathlib2 import Path
from setuptools import setup

setup(
    name="anode",
    version="10.100.1000.dev0" if "$" in "$SERVICE_VERSION_ABSOLUTE" else "$SERVICE_VERSION_ABSOLUTE".replace("-SNAPSHOT", ".dev0"),
    description=" asystem anode",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "License :: Other/Proprietary License",
        "Programming Language :: Python :: 2.7",
        "Topic :: Other/Nonlisted Topic",
    ],
    keywords="asystem anode",
    url="https://github.com/ggear/asystem/tree/master/asystem-anode",
    author="Graham Gear",
    author_email="notmyemail@company.com",
    packages=setuptools.find_packages(where='main/python', include=['anode', 'anode.*']),
    package_dir={'': 'main/python'},
    install_requires=Path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "reqs_run.txt")).read_text().split("\n"),
    tests_require=["mock"],
    test_suite="test",
    setup_requires=["setuptools_trial"],
    entry_points={"console_scripts": ["anode=anode.anode:main"]},
    include_package_data=True,
    zip_safe=False
)
