#!/bin/bash -e

test_name="cpu"

if [ "$#" -ne 3 ]; then
    cat <<-ENDOFMESSAGE
Please specify the base result file and the result file, as well as the output file as arguments.
The result file should be named in this format: <limits>_<machine>_${test_name}_<opts>.prof (e.g. without_kv3_cpu_20000.prof)

Usage: ./parse_${test_name}.sh <base result file> <result file> <output file>
ENDOFMESSAGE
    exit
fi

mkdir -p $(dirname $3)

header="machine,limits,benchmark,base_result,lower_is_better,result"
if [ ! -f "$3" ] || ! ggrep -q "$header" "$3"; then
    echo "$header" | tee "$3"
fi

bn=`basename "$2" ".prof"`

res_test_name=`echo "$bn" | cut -d _ -f 3`
if [ "${res_test_name}" != "${test_name}" ]; then
    echo "Please check the if result file is from ${test_name} test. (Current test name: $res_test_name)"
    exit
fi

opts=`echo "$bn" | cut -d _ -f 4-`
machine=`echo "$bn" | cut -d _ -f 2`
limits=`echo "$bn" | cut -d _ -f 1`

p_time="total time:\s+\K[\d\.]+"

base_res=`ggrep -oP "$p_time" $1`
res=`ggrep -oP "$p_time" $2`

echo "$machine,$limits,sysbench_${test_name}_${opts},$base_res,True,$res" | tee -a "$3"
