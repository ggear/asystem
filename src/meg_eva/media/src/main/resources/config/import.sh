#!/bin/bash

IMPORT_MEDIA_SHARE=/share/3/tmp

if [ -b /dev/sdb1 ] && [ -d ${IMPORT_MEDIA_SHARE} ]; then
  mkdir -p /media/usbdrive
  umount -fq /media/usbdrive
  mount /dev/sdb1 /media/usbdrive
  if [ -d /media/usbdrive ]; then
    echo "Copying /media/usbdrive to ${IMPORT_MEDIA_SHARE} ... "
    rsync -avP /media/usbdrive ${IMPORT_MEDIA_SHARE}
    echo "Copy /media/usbdrive to ${IMPORT_MEDIA_SHARE} complete"
    echo "Metadata commands:"
    echo "umount -fq /media/usbdrive"
    echo "mount /dev/sdb1 /media/usbdrive"
    echo "pgsrip *.mkv"
    echo "rename -v 's/(.*)S([0-9][0-9])E([0-9][0-9])\..*\.mkv/\$1s\$2e\$3.mkv/' *.mkv"
    echo "ffmpeg -f concat -i files.txt -c copy -aspect 16/9 output.mkv"
    echo "ffmpeg -i input.avi -c:v h264_videotoolbox -vf "scale=1920:1080,setdar=16/9" -aspect 16:9 -q:v 100 -c:a aac -b:a 256k output.mkv"
    echo "find . -name \"*.mkv\" -exec echo mediainfo \"'--Output=Audio;[%Language/String%, ][%BitRate/String%, ][%SamplingRate/String%, ][%BitDepth/String%, ][%Channel(s)/String%, ]%Format%\n'\" \\\"{}\\\" \;"
    echo 'find . -name "*.mkv" -exec echo ffmpeg -i \"{}\" -c:v copy -ac 6 -ar 48000 -ab 400k -c:a aac \"/data/media/movies/{}\" \;'
  fi
fi
