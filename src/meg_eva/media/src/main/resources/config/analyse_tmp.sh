#!/bin/bash


# TODO: Build a non-Plex, Macbook ffmpeg on-demand optimise script - maybe only do this?






ROOT_DIR=$(dirname $(readlink -f "$0"))

. ${ROOT_DIR}/../.env

IFS=$'\n'
for VERSIONS in $(find "/share" -type f -path '*/Plex Versions/*/*.mp4' ! -path '.inProgress'); do
  echo "${VERSIONS}"
done





#echo -n "Refreshing libraries ... "
#for PLEX_LIBRARY_KEY in $(curl -sf http://${PLEX_SERVICE}:${PLEX_HTTP_PORT}/library/sections?X-Plex-Token=${PLEX_TOKEN} | xq -x '/MediaContainer/Directory/@key'); do
#  curl -sf http://${PLEX_SERVICE}:${PLEX_HTTP_PORT}/library/sections/${PLEX_LIBRARY_KEY}/refresh?X-Plex-Token=${PLEX_TOKEN}
#done
#echo "done"

# Detect completed 'Plex Versions'
# Move Season/Movie out of tree
# Refresh Library
# Move Season/Moive backinto tree, replacing original
# Rename files, adding prefix, removing srt suffix
# remove empty 'Plex Versions' dirs
# Refresh Library

# TODO: Check versions not queued up to be recreated, they seem to be with the process, maybe dont do at all and just re-encode out of plex band?


echo "-" && find . -type f \( -iname \*.mp4 -o -iname \*.mkv -o -iname \*.avi \) -exec ls -lah {} \; -exec ffprobe -v quiet -select_streams v:0 -show_entries stream=width,height -of default=noprint_wrappers=1:nokey=0 {} \; -exec ffprobe -v quiet -select_streams v:0 -show_entries format=bit_rate -of default=noprint_wrappers=1:nokey=0 {} \; -exec echo "-" \;

# 10x on RAE on SSD, 8x on RAE on LAN, 4x on RAE/ZOE on WiFi,
other-transcode ../Deadpool\ \(2016\).mkv --target 1080p=8000
ffmpeg -codec:0 hevc -codec:1 dca -analyzeduration 20000000 -probesize 20000000 -i Deadpool\ \(2016\).mkv -filter_complex [0:0]scale=w=1920:h=804:force_divisible_by=4[0];[0]format=p010,tonemap=mobius[1];[1]format=pix_fmts=yuv420p|nv12[2] -map [2] -codec:0 libx264 -crf:0 16 -maxrate:0 8000k -bufsize:0 16000k -r:0 23.975999999999999 -preset:0 veryfast -level:0 4.0 -x264opts:0 subme=0:me_range=4:rc_lookahead=10:me=dia:no_chroma_me:8x8dct=0:partitions=none -filter_complex [0:1] aresample=async=1:ochl='5.1':rematrix_maxval=0.000000dB:osr=48000[3] -map [3] -metadata:s:1 language=eng -codec:1 aac -b:1 768k -map 0:2 -metadata:s:2 language=eng -codec:2 copy -copypriorss:2 0 -map 0:3 -metadata:s:3 language=dan -codec:3 copy -copypriorss:3 0 -map 0:4 -metadata:s:4 language=fin -codec:4 copy -copypriorss:4 0 -map 0:5 -metadata:s:5 language=nor -codec:5 copy -copypriorss:5 0 -map 0:6 -metadata:s:6 language=swe -codec:6 copy -copypriorss:6 0 -f mp4 -map_metadata -1 -map_chapters -1 -movflags +faststart ./Plex\ Versions/Optimized\ by\ FFmpeg/.inProgress/Deadpool\ \(2016\).mp4.935 -map 0:12 -metadata:s:0 language=eng -codec:0 copy -strict_ts:0 0 -f srt ./Plex\ Versions/Optimized\ by\ FFmpeg/.inProgress/Deadpool\ \(2016\).mp4.935.89498.sidecar -map 0:13 -metadata:s:0 language=eng -codec:0 copy -strict_ts:0 0 -f srt ./Plex\ Versions/Optimized\ by\ FFmpeg/.inProgress/Deadpool\ \(2016\).mp4.935.89499.sidecar -map 0:14 -metadata:s:0 language=dan -codec:0 copy -strict_ts:0 0 -f srt ./Plex\ Versions/Optimized\ by\ FFmpeg/.inProgress/Deadpool\ \(2016\).mp4.935.89500.sidecar -map 0:15 -metadata:s:0 language=fin -codec:0 copy -strict_ts:0 0 -f srt ./Plex\ Versions/Optimized\ by\ FFmpeg/.inProgress/Deadpool\ \(2016\).mp4.935.89501.sidecar -map 0:16 -metadata:s:0 language=nor -codec:0 copy -strict_ts:0 0 -f srt ./Plex\ Versions/Optimized\ by\ FFmpeg/.inProgress/Deadpool\ \(2016\).mp4.935.89502.sidecar -map 0:17 -metadata:s:0 language=swe -codec:0 copy -strict_ts:0 0 -f srt ./Plex\ Versions/Optimized\ by\ FFmpeg/.inProgress/Deadpool\ \(2016\).mp4.935.89503.sidecar -y -nostats -loglevel quiet -loglevel_plex error -progressurl http://127.0.0.1:32400/video/:/transcode/session/9404cde5-f816-421f-9191-48f70fbd7af7/edde7b96-a6c7-45c2-87ca-2b7d37cf9dda/progress

# Optimized for TV – 8 Mbps 1080p
# TV Quaility Optimised (0.1-0.9x, 3.5h, 6.1G)
# /usr/lib/plex mediaserver/Plex Transcoder -codec:0 hevc -codec:1 dca -analyzeduration 20000000 -probesize 20000000 -i /share/3/media/parents/movies/Force Of Nature (2024)/Force Of Nature (2024).mkv -filter_complex [0:0]scale=w=1920:h=800:force_divisible_by=4[0];[0]format=p010,tonemap=mobius[1];[1]format=pix_fmts=yuv420p|nv12[2] -map  [2] -metadata:s:0 language=eng -codec:0 libx264 -crf:0 16 -maxrate:0 8000k -buf size:0 16000k -r:0 24 -preset:0 veryfast -level:0 4.0 -x264opts:0 subme=0:me_ran ge=4:rc_lookahead=10:me=dia:no_chroma_me:8x8dct=0:partitions=none -filter_comple x [0:1] aresample=async=1:ochl='5.1':rematrix_maxval=0.000000dB:osr=48000[3] -ma p [3] -metadata:s:1 language=eng -codec:1 aac -b:1 768k -map 0:2 -metadata:s:2 language=eng -codec:2 copy -copypriorss:2 0 -f mp4 -map_metadata -1 -map_chapters  -1 -movflags +faststart /share/3/media/parents/movies/Force Of Nature (2024)/Pl ex Versions/Optimized for TV/.inProgress/Force of Nature_ The Dry 2 (2024).mp4.8 82 -map 0:4 -metadata:s:0 language=deu -codec:0 copy -strict_ts:0 0 -f srt /shar e/3/media/parents/movies/Force Of Nature (2024)/Plex Versions/Optimized for TV/. inProgress/Force of Nature_ The Dry 2 (2024).mp4.882.100985.sidecar -y -nostats  -loglevel quiet -loglevel_plex error -progressurl http://127.0.0.1:32400/video/: /transcode/session/ea2a4283-1cec-40cd-831f-f679f2e02db1/381b1c7a-bfc1-483d-a58a- 28f607e60245/progress

# Original Quality Optimised (0.1-0.6x, 8.5h, 27G)
