#!/bin/bash

# Mounting
umount -fq /media/usbdrive
[ $(lsblk -ro name,label | grep GRAHAM | wc -l) -eq 1 ] && mount -t exfat $(echo "/dev/"$(lsblk -ro name,label | grep GRAHAM | awk 'BEGIN{RAR_FILES=ORAR_FILES=" "}{print $1}')) /media/usbdrive

# Renaming
rename -v 's/X/Y/' ./*.mkv
rename -v 's/Season /Season 0/' Season\ ?/
rename -v 's/(.*)[sS]([0-9][0-9])[eE]([0-9][0-9])\..*\.mkv/$1s$2e$3.mkv/' ./*.mkv
find . -name "*TRANS*mkv" -exec rename -vf 's/__TRANSCODE_MID//' "{}" \;
find . -name "*TRANS*mkv" -exec rename -vf 's/__TRANSCODE_MIN//' "{}" \;

# Merge
open *__TRANS*mkv
rename -vf 's/__TRANSCODE_MID//' *__TRANS*mkv
find . -name '._defaults_analysed_*TRANS*_mkv.yaml' ! -name '*_M*_mkv.yaml'
find . -name '._defaults_analysed_*TRANS*_mkv.yaml' ! -name '*_M*_mkv.yaml' -delete
find . -name '._defaults_analysed_*TRANS*_mkv.yaml'
find . -name '._defaults_analysed_*TRANS*_mkv.yaml' -exec rename -v -f 's/_analysed_/_merged_/' "{}" \;
find . -name '._defaults_merged_*TRANS*_mkv.yaml' -exec rename -v -f 's/__TRANSCODE_.*_mkv/_mkv/' "{}" \;
find . -name '._defaults_analysed_*TRANS*_mkv.yaml'

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
echo "-" && find . -type f \( -iname \*.mp4 -o -iname \*.mkv -o -iname \*.avi \) -exec ls -lah {} \; -exec ffprobe -v quiet -select_streams v:0 -show_entries stream=width,height -of default=noprint_wrappers=1:nokey=0 {} \; -exec ffprobe -v quiet -select_streams v:0 -show_entries format=bit_rate -of default=noprint_wrappers=1:nokey=0 {} \; -exec echo "-" \;

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
find . -type f -exec ffmpeg -y -i {} -c:v copy -c:a copy -map 0:0 -map 0:2 {}.mkv \;     # Global indexing
find . -type f -exec ffmpeg -y -i {} -c:v copy -c:a copy -map 0:v:0 -map 0:a:1 {}.mkv \; # Type indexing

# Convert PGS subtitles to SRT
pgsrip ./*.mkv

# Copy between shares
rsync -avhPr /share/3/media/kids /share/2/media

# Copy media to usb-drive
find "/share/*/media/parents/movies -name *Hope*mkv" -exec echo "     '{}' \\" \;
nohup rsync -avhPr --no-perms --no-owner --no-group \
  '/share/3/media/parents/movies/A New Hope (1977)/A New Hope (1977).mkv' \
  '/media/usbdrive/Movies' &
disown
find "/share/*/media/parents/series -name *Last*mkv" -exec echo "     '{}' \\" \;
SERIES='The Last Of Us'
nohup mkdir -p "/media/usbdrive/Shows/${SERIES}" && rsync -avhPr --no-perms --no-owner --no-group \
  '/share/5/media/parents/series/The Last Of Us/Season 1/The Last Of Us S01E01.mkv' \
  '/share/5/media/parents/series/The Last Of Us/Season 1/The Last Of Us S01E02.mkv' \
  '/share/5/media/parents/series/The Last Of Us/Season 1/The Last Of Us S01E03.mkv' \
  '/share/5/media/parents/series/The Last Of Us/Season 1/The Last Of Us S01E04.mkv' \
  "/media/usbdrive/Shows/${SERIES}" &
disown

# Delete subtitles
for f in *.mkv; do ffmpeg -i "$f" -map 0 -map -0:s -c copy -y "temp.mkv" && mv "temp.mkv" "$f"; done

# Add subtitles
pip install subliminal ffsubsync
subliminal download -l en *.mkv
for f in *.mkv; do
  s="${f%.mkv}.en.srt"
  if [ -f "$s" ]; then
    echo "Syncing $s to $f"
    ffsubsync "$f" -i "$s" -o "${f%.mkv}.en.synced.srt"
  else
    echo "Subtitle $s not found for $f"
  fi
done
for f in *.mkv; do
  s="${f%.mkv}.en.synced.srt"
  [ -f "$s" ] && ffmpeg -i "$f" -i "$s" -map 0 -map 1 -c copy \
    -metadata:s:s:0 language=eng -metadata:s:s:0 title="English" \
    -y "temp.mkv" && mv "temp.mkv" "$f"
done
rm -rf *.srt

# Audio EAC3 to AC3
ffmpeg -i 'Youre Cordially Invited (2025).mkv' \
  -map 0 -c:v copy -c:s copy -c:a ac3 -b:a 640k \
  'Youre Cordially Invited (2025)_ac3.mkv'

# Convert AVI to MKV container, addint timing data
for f in *.avi; do
  ffmpeg -fflags +genpts -i "$f" -c copy "${f%.avi}__TRANSCODE_MKV.mkv"
done

# Remove broken subtitles
temp_sub="temp_sub.srt"
find . -type f -name '*.mkv' -print0 | while IFS= read -r -d '' file; do
  echo "Processing file: [$file]"
  map_args=("-map" "0")
  changed=0
  while IFS= read -r idx; do
    if ffmpeg -v error -y -i "$file" -map 0:s:$idx -c:s srt "$temp_sub" >/dev/null 2>&1; then
      if [ ! -s "$temp_sub" ]; then
        map_args+=("-map" "-0:s:$idx")
        changed=1
      fi
    else
      map_args+=("-map" "-0:s:$idx")
      changed=1
    fi
  done < <(ffprobe -v error -select_streams s -show_entries stream=index -of csv=p=0 "$file")
  rm -f "$temp_sub"
  if [ "$changed" -eq 1 ]; then
    dir=$(dirname "$file")
    base=$(basename "$file" .mkv)
    out="$dir/${base}__TRANSCODE_SUB.mkv"
    ffmpeg -loglevel error -y -i "$file" "${map_args[@]}" -c copy "$out" >/dev/null 2>&1
    echo "✅ Changed: $file → ${base}__TRANSCODE_SUB.mkv"
  else
    echo "➖ Unchanged: $file"
  fi
done

# Nohup a script
nohup asystem-media-reformat >/tmp/asystem-media-clean.log 2>&1 &
disown

# Process video
ffmpeg -i "input.mov" -vcodec hevc_videotoolbox -b:v 500k -n "output.mov"
ffmpeg -i "input.mov" -vcodec h264_videotoolbox -b:v 500k -n "output.mov"
ffmpeg -f concat -i files.txt -c copy -aspect 16/9 output.mkv
ffmpeg -i input.avi -c:v h264_videotoolbox -vf "scale=1920:1080,setdar=16/9" -aspect 16:9 -q:v 100 -c:a aac -b:a 256k output.mkv
find . -name "*.mkv" -exec echo ffmpeg -i "{}" -c:v copy -ac 6 -ar 48000 -ab 400k -c:a aac "/data/media/movies/{}" \;
