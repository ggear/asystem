# ASystem

A home data, analytics and automation system.

## Requirements

To build, test and package this project the following is required:

* go-1.20+
* rust-1.5+
* cargo-1.5+
* conda-4.5.12+
* fabric-2.5+
* docker-19+
* docker-compose-1.26+

## Layout

Each module is specified by at least one `host-label`, multiple hosts demarcated by the `_`
character and a globally unique `service-name` directory as per specification:

`module/<host-label>[_<host-label>]*/<service-name>`
