#!/bin/bash

umount -fq /media/usbdrive
[ $(lsblk -ro name,label | grep GRAHAM | wc -l) -eq 1 ] && mount $(echo "/dev/"$(lsblk -ro name,label | grep GRAHAM | awk 'BEGIN{FS=OFS=" "}{print $1}')) /media/usbdrive

rename -v 's/(.*)s([0-9][0-9])e([0-9][0-9])\..*\.mkv/\$1s\$2e\$3.mkv/' *.mkv
rename -v 's/(.*)S([0-9][0-9])E([0-9][0-9])\..*\.mkv/\$1s\$2e\$3.mkv/' *.mkv

mediainfo *.mkv
find . -name "*.mkv" -exec echo mediainfo "'--Output=Audio;[%Language/String%, ][%BitRate/String%, ][%SamplingRate/String%, ][%BitDepth/String%, ][%Channel(s)/String%, ]%Format%\n'" \"{}\" \;

pgsrip *.mkv
ffmpeg -f concat -i files.txt -c copy -aspect 16/9 output.mkv
ffmpeg -i input.avi -c:v h264_videotoolbox -vf "scale=1920:1080,setdar=16/9" -aspect 16:9 -q:v 100 -c:a aac -b:a 256k output.mkv
find . -name "*.mkv" -exec echo ffmpeg -i "{}" -c:v copy -ac 6 -ar 48000 -ab 400k -c:a aac "/data/media/movies/{}" \;
