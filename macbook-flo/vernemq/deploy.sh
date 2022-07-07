#!/bin/sh

export $(xargs <.env)

./src/main/resources/config/publish.sh
