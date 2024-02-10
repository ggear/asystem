#!/bin/bash -e

test_name="memory"

if [ "$#" -ne 3 ]; then
    cat <<-ENDOFMESSAGE
Please specify the base result file and the result file, as well as the output file as arguments.
The result should be named in this format: <limits>_<machine>_${test_name}_<opts>.prof (e.g. without_kv3_memory_seq.prof)

Usage: ./parse_${test_name}.sh <base result file> <result file> <output file>
ENDOFMESSAGE
    exit
fi

mkdir -p $(dirname $3)

header="machine,limits,benchmark,base_result,lower_is_better,result"
if [ ! -f "$3" ] || ! grep -q "$header" "$3"; then
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

p_ops="[\d\.]+(?= ops/sec)"

base_res=`grep -oP "$p_ops" $1`
res=`grep -oP "$p_ops" $2`

echo "$machine,$limits,sysbench_${test_name}_${opts},$base_res,False,$res" | tee -a "$3"
