#!/bin/bash

FILE_VIDEO="Video.mkv"
FILE_SUBTITLES="sub.srt"
FILE_LIB="libx265"
#FILE_COLOUR="bt709"
FILE_COLOUR="bt2020"
#FILE_RESOLUTION="384x206"
FILE_RESOLUTION="1280x720"
#FILE_RESOLUTION="1920x1080"
#FILE_RESOLUTION="3840x2160"
FILE_SIZE_1_RIGHT=75
#FILE_SIZE_1_LARGE=150

if [ ! -f "${FILE_SUBTITLES}" ]; then
  i=0
  j=1
  while (($i < 10)); do
    s+="$j
00:00:$(printf %02d $i),0 --> 00:00:$(printf %02d $j),0
from $i to $j

"
    ((i++))
    ((j++))
  done
  echo "$s" >"${FILE_SUBTITLES}"
fi

ffmpeg -y \
  -f lavfi -i testsrc=size="${FILE_RESOLUTION}":rate="${FILE_SIZE_1_RIGHT}" \
  -f lavfi -i sine=220:1:44100 \
  -f lavfi -i sine=440:2:44100 \
  -f lavfi -i sine=880:3:44100 \
  -i "${FILE_SUBTITLES}" \
  -i "${FILE_SUBTITLES}" \
  -i "${FILE_SUBTITLES}" \
  -i "${FILE_SUBTITLES}" \
  -i "${FILE_SUBTITLES}" \
  -map 0 -map 1 -map 2 -map 3 -map 4 -map 5 -map 6 -map 7 -map 8 \
  -c:v "${FILE_LIB}" \
  -preset slow \
  -b:v 8M \
  -color_primaries ${FILE_COLOUR} \
  -x265-params "colorprim=${FILE_COLOUR}" \
  -metadata:s:v:0 "color_primaries=${FILE_COLOUR}" \
  -c:a:0 ac3 \
  -c:a:1 mp3 \
  -c:a:2 aac \
  -c:s ass \
  -metadata:s:a:0 language=fra \
  -metadata:s:a:1 language=ger \
  -metadata:s:a:2 language=eng \
  -metadata:s:s:0 language=fra \
  -metadata:s:s:1 language=ger \
  -metadata:s:s:2 language=ger \
  -metadata:s:s:3 language=eng \
  -metadata:s:s:4 language=eng -t 10 "${FILE_VIDEO}"

rm -rf "${FILE_SUBTITLES}"
