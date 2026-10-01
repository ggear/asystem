#!/bin/bash

if [ -e /dev/ttyUSBTempProbe ]; then
  chmod 666 /dev/ttyUSBTempProbe
fi
