# ASystem

A home data, analytics and automation system monorepo.

## Requirements

To build, test and package this project the following is required:

* python-3+
* fabric-2.5+
* conda-20+
* docker-19+
* docker-compose-1.26+

The following programming toolchains are installed with the required version levels and
dependencies into an isolated, dedicated Conda environment on project setup:

* go
* rust
* python

## Layout

Each module is specified by at least one `host-label`, multiple hosts demarcated by the `_`
character and a globally unique `service-name` directory as per specification:

`src/<host-label>[_<host-label>]*/<service-name>`
