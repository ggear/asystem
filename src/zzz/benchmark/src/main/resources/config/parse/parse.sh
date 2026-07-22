#!/bin/bash -e

if [ "$#" -ne 3 ]; then
    cat <<-ENDOFMESSAGE
Please specify the base result file and the result file, as well as the output file as arguments.
The result file should be named in this format: <limits>_<machine>_<test-name>_<opts>.prof (e.g. without_kv3_fileio_seqrewr.prof)

Usage: ./parse.sh <base result file> <result file> <output file>
ENDOFMESSAGE
    exit
fi

bn=`basename "$1" ".prof"`
test_name=`echo "$bn" | cut -d _ -f 3`

script_path=`dirname $(readlink -f $0)`

if [ -f "${script_path}/parse_${test_name}.sh" ]; then
    ${script_path}/parse_${test_name}.sh "$@"
else
    echo "Unsupported test name: $test_name"
fi
