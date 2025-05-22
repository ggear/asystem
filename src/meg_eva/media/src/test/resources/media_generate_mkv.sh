#!/bin/bash

if [ ! -f in.srt ]; then
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
  echo "$s" >in.srt
fi

ffmpeg -y \
  -f lavfi -i testsrc=size=384x206:rate=1 \
  -f lavfi -i sine=220:1:44100 \
  -f lavfi -i sine=440:2:44100 \
  -f lavfi -i sine=880:3:44100 \
  -i in.srt \
  -i in.srt \
  -i in.srt \
  -i in.srt \
  -i in.srt \
  -map 0 -map 1 -map 2 -map 3 -map 4 -map 5 -map 6 -map 7 -map 8 \
  -c:v libx264 \
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
  -metadata:s:s:4 language=eng -t 10 Video.mkv

rm -rf in.srt
ffprobe Video.mkv
mpv Video.mkv
