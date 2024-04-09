#!/bin/bash

# Mounting
umount -fq /media/usbdrive
[ $(lsblk -ro name,label | grep GRAHAM | wc -l) -eq 1 ] && mount -t exfat $(echo "/dev/"$(lsblk -ro name,label | grep GRAHAM | awk 'BEGIN{RAR_FILES=ORAR_FILES=" "}{print $1}')) /media/usbdrive

# Renaming
rename -v 's/X/Y/' ./*.mkv
rename -v 's/(.*)[sS]([0-9][0-9])[eE]([0-9][0-9])\..*\.mkv/$1s$2e$3.mkv/' ./*.mkv

# Extract RAR files
ROOT_DIR=$PWD
for RAR_FILE in $(find . -name ./*.rar -exec echo {} \;); do
  cd $(dirname $RAR_FILE)
  unrar x $(basename $RAR_FILE)
  cd $ROOT_DIR
done

# Media metadata
find . -type f -exec echo mediainfo {} \; -exec echo -- \; -exec mediainfo {} \; | less
find . -type f -exec echo mediainfo {} \; -exec echo -- \; -exec mediainfo '--Output=Audio;[%Language/String%, ][%BitRate/String%, ][%SamplingRate/String%, ][%BitDepth/String%, ][%Channel(s)/String%, ]%RAR_FILEormat%\n' {} \;

# Media streams
find . -type f -exec echo ffprobe -i {} \; -exec ffprobe -i {} \; 2>&1 | less
find . -type f -exec echo ffprobe -i {} \; -exec sh -c 'ffprobe -i "{}" 2>&1 | grep "Stream #"' \;

# Copy into a new container format
find . -type f -exec ffmpeg -y -i {} -c:v copy -c:a copy {}.mkv \;

# Copy specific streams (video 0, audio 2), dropping all others
#  Stream #0:0(eng): Video: h264 (High), yuv420p(tv, bt709, progressive), 1920x1080 [SAR 1:1 DAR 16:9], 23.98 fps, 23.98 tbr, 1k tbn (default)
#  Stream #0:1(ita): Audio: ac3, 48000 Hz, 5.1(side), fltp, 448 kb/s (default)
#  Stream #0:2(eng): Audio: ac3, 48000 Hz, 5.1(side), fltp, 448 kb/s
#  Stream #0:3(ita): Subtitle: dvd_subtitle, 720x576
#  Stream #0:4(eng): Subtitle: dvd_subtitle, 720x576
find . -type f -exec ffmpeg -y -i {} -c:v copy -c:a copy -map 0:0 -map 0:2 {}.mkv \;       # Global indexing
find . -type f -exec ffmpeg -y -i {} -c:v copy -c:a copy -map 0:v:0 -map 0:a:1 {}.mkv \;   # Type indexing

# Convert PGS subtitles to SRT
pgsrip ./*.mkv

# Copy between shares
rsync -avhPr /share/3/media/kids /share/2/media

# TODO: Update all for find and cull to only useful commands
ffmpeg -i "input.mov" -vcodec hevc_videotoolbox -b:v 500k -n "output.mov"
ffmpeg -i "input.mov" -vcodec h264_videotoolbox -b:v 500k -n "output.mov"
ffmpeg -f concat -i files.txt -c copy -aspect 16/9 output.mkv
ffmpeg -i input.avi -c:v h264_videotoolbox -vf "scale=1920:1080,setdar=16/9" -aspect 16:9 -q:v 100 -c:a aac -b:a 256k output.mkv
find . -name "*.mkv" -exec echo ffmpeg -i "{}" -c:v copy -ac 6 -ar 48000 -ab 400k -c:a aac "/data/media/movies/{}" \;
