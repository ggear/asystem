#!/bin/bash

IMPORT_MEDIA_SHARE=/share/3/tmp

if [ $(lsblk -ro name,label | grep GRAHAM | wc -l) -eq 1 ]; then
  IMPORT_MEDIA_DEV="/dev/"$(lsblk -ro name,label | grep GRAHAM | awk 'BEGIN{FS=OFS=" "}{print $1}')
  if [ -a ${IMPORT_MEDIA_DEV} ]; then
    echo "Starting copy of [/media/usbdrive] from [${IMPORT_MEDIA_DEV}] to [${IMPORT_MEDIA_SHARE}]"
    mkdir -p /media/usbdrive
    umount -fq /media/usbdrive
    mount ${IMPORT_MEDIA_DEV} /media/usbdrive
    find /media/usbdrive -name "\.*" -exec rm {} \;
    rm -rf /media/usbdrive/\.* /media/usbdrive/System* /media/usbdrive/\$RECYCLE.BIN
    rsync -avP /media/usbdrive/* ${IMPORT_MEDIA_SHARE}
    umount -fq /media/usbdrive
    echo "Completed copy of [/media/usbdrive] from [${IMPORT_MEDIA_DEV}] to [${IMPORT_MEDIA_SHARE}]"
    echo "Metadata commands:"
    echo "umount -fq /media/usbdrive"
    echo "mount ${IMPORT_MEDIA_DEV} /media/usbdrive"
    echo "pgsrip *.mkv"
    echo "rename -v 's/(.*)S([0-9][0-9])E([0-9][0-9])\..*\.mkv/\$1s\$2e\$3.mkv/' *.mkv"
    echo "ffmpeg -f concat -i files.txt -c copy -aspect 16/9 output.mkv"
    echo "ffmpeg -i input.avi -c:v h264_videotoolbox -vf "scale=1920:1080,setdar=16/9" -aspect 16:9 -q:v 100 -c:a aac -b:a 256k output.mkv"
    echo "find . -name \"*.mkv\" -exec echo mediainfo \"'--Output=Audio;[%Language/String%, ][%BitRate/String%, ][%SamplingRate/String%, ][%BitDepth/String%, ][%Channel(s)/String%, ]%Format%\n'\" \\\"{}\\\" \;"
    echo 'find . -name "*.mkv" -exec echo ffmpeg -i \"{}\" -c:v copy -ac 6 -ar 48000 -ab 400k -c:a aac \"/data/media/movies/{}\" \;'
  fi
fi