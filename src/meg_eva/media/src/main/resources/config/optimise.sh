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


# TV Quaility Optimised (0.1-0.9x, 3.5h, 6.1G)
# /usr/lib/plex mediaserver/Plex Transcoder -codec:0 hevc -codec:1 dca -analyzeduration 20000000  -probesize 20000000 -i /share/3/media/parents/movies/Force Of Nature (2024)/For ce Of Nature (2024).mkv -filter_complex [0:0]scale=w=1920:h=800:force_divisible_ by=4[0];[0]format=p010,tonemap=mobius[1];[1]format=pix_fmts=yuv420p|nv12[2] -map  [2] -metadata:s:0 language=eng -codec:0 libx264 -crf:0 16 -maxrate:0 8000k -buf size:0 16000k -r:0 24 -preset:0 veryfast -level:0 4.0 -x264opts:0 subme=0:me_ran ge=4:rc_lookahead=10:me=dia:no_chroma_me:8x8dct=0:partitions=none -filter_comple x [0:1] aresample=async=1:ochl='5.1':rematrix_maxval=0.000000dB:osr=48000[3] -ma p [3] -metadata:s:1 language=eng -codec:1 aac -b:1 768k -map 0:2 -metadata:s:2 language=eng -codec:2 copy -copypriorss:2 0 -f mp4 -map_metadata -1 -map_chapters  -1 -movflags +faststart /share/3/media/parents/movies/Force Of Nature (2024)/Pl ex Versions/Optimized for TV/.inProgress/Force of Nature_ The Dry 2 (2024).mp4.8 82 -map 0:4 -metadata:s:0 language=deu -codec:0 copy -strict_ts:0 0 -f srt /shar e/3/media/parents/movies/Force Of Nature (2024)/Plex Versions/Optimized for TV/. inProgress/Force of Nature_ The Dry 2 (2024).mp4.882.100985.sidecar -y -nostats  -loglevel quiet -loglevel_plex error -progressurl http://127.0.0.1:32400/video/: /transcode/session/ea2a4283-1cec-40cd-831f-f679f2e02db1/381b1c7a-bfc1-483d-a58a- 28f607e60245/progress

# Original Quality Optimised (0.1-0.6x, 8.5h, 27G)
