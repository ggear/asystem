#!/bin/bash -e

test_name="fileio"

if [ "$#" -ne 3 ]; then
    cat <<-ENDOFMESSAGE
Please specify the base result file and the result file, as well as the output file as arguments.
The result file should be named in this format: <limits>_<machine>_${test_name}_<opts>.prof (e.g. without_kv3_fileio_seqrewr.prof)

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

pt() {
    echo "$1\D+\K[\d\.]+"
}

prt() {
    echo "$machine,$limits,sysbench_${test_name}_${opts}_$1,$2,False,$3" | tee -a "$4"
}


# calculate events/min
kw='total number of events:'
base_evs=`ggrep -oP "$(pt "$kw")" $1`
evs=`ggrep -oP "$(pt "$kw")" $2`

kw='total time:'
base_res=`ggrep -oP "$(pt "$kw")"  $1`
res=`ggrep -oP "$(pt "$kw")" $2`

base_res=`echo "scale=4; ${base_evs}/${base_res}*60" | bc`
res=`echo "scale=4; ${evs}/${res}*60" | bc`

desc='events_per_min'
prt "$desc" "$base_res" "$res" "$3"


# calculate req/min
kw='writes/s:'
base_res=`ggrep -oP "$(pt "$kw")"  $1`
res=`ggrep -oP "$(pt "$kw")" $2`

base_res=`echo "scale=4; ${base_res}*60" | bc`
res=`echo "scale=4; ${res}*60" | bc`

desc='req_per_min'
prt "$desc" "$base_res" "$res" "$3"


# calculate BW in MiB/s
if [[ $opts == *"_seqwr_"* ]] || [[ $opts == *"_rndwr_"* ]]; then
    kw='written, MiB/s:'
elif [[ $opts == *"_seqrd_"* ]] || [[ $opts == *"_rndrd_"* ]]; then
    kw='read, MiB/s:'
fi

# The proper way to check if a variable is set
# http://stackoverflow.com/questions/3601515/how-to-check-if-a-variable-is-set-in-bash
if [ ! -z "${kw+x}" ]; then
    base_res=`ggrep -oP "$(pt "$kw")"  $1`
    res=`ggrep -oP "$(pt "$kw")" $2`

    desc='bw_mib_per_sec'
    prt "$desc" "$base_res" "$res" "$3"
else
    echo "Unsupported file-test-mode, it must be one of {seqwr, seqrd, rndrd, rndwr}" 1>&2    
    exit 1
fi
