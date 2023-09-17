#!/bin/bash

echo -n "Normalising /data ... "
setfacl -bR /data/media
find /data/media -type f -exec chmod 644 {} \;
find /data/media -type d -exec chmod 755 {} \;
find /data -type f -name nohup -exec rm -f {} \;
find /data -type f -name .DS_Store -exec rm -f {} \;
echo "done"

import_files() {
  if [ -b /dev/sdb1 ] && [ -d /data/media/${1} ]; then
    mkdir -p /media/usbdrive
    umount -fq /media/usbdrive
    mount /dev/sdb1 /media/usbdrive
    if [ -d /media/usbdrive/${1} ]; then
      echo "Copying /media/usbdrive/${1} to /data/tmp/${1} ... "
      rsync -avP /media/usbdrive/${1} /data/tmp
      echo "Copy /media/usbdrive/${1} to /data/tmp/${1} complete"
      echo "Metadata commands:"
      echo "umount -fq /media/usbdrive"
      echo "mount /dev/sdb1 /media/usbdrive"
      echo "rename -v 's/(.*)S([0-9][0-9])E([0-9][0-9])\..*\.mkv/\$1s\$2e\$3.mkv/' *.mkv"
      echo "ffmpeg -f concat -i files.txt -c copy -aspect 16/9 output.mkv"
      echo "ffmpeg -i input.avi -c:v h264_videotoolbox -vf "scale=1920:1080,setdar=16/9" -aspect 16:9 -q:v 100 -c:a aac -b:a 256k output.mkv"
      echo "find . -name \"*.mkv\" -exec echo mediainfo \"'--Output=Audio;[%Language/String%, ][%BitRate/String%, ][%SamplingRate/String%, ][%BitDepth/String%, ][%Channel(s)/String%, ]%Format%\n'\" \\\"{}\\\" \;"
      echo 'find . -name "*.mkv" -exec echo ffmpeg -i \"{}\" -c:v copy -ac 6 -ar 48000 -ab 400k -c:a aac \"/data/media/movies/{}\" \;'
    fi
  fi
}

import_files audio
import_files movies
import_files series
