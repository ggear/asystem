# ASystem

A home data, analytics and automation system.

## Requirements
To build, test and package this project the following is required:
* go-1.14+
* rust-1.5+
* cargo-1.5+
* conda-4.6+
* fabric-2.5+
* docker-19+
* docker-compose-1.26+

## Layout
Each service is specified by at least one `host` name, multiple names demarcated by the `_` 
character and a globally unique `service` name as per:

`<host>[_<host>[_<host]]/<service>`
