#!/bin/bash

chown -R nobody:nogroup media
setfacl -bR media
chmod -R 644 media
chmod -R a+rwX media
chmod +x ./repair.sh
find . -type f -name .DS_Store -exec rm -f {} \;



# mount /dev/sdc1 /media/cdrom
# rsync -avP /media/cdrom/TV/XX /data/media/Series/XX
# rename -v s/\ .*mkv/\.mkv/ Battlestar-Galactica_s04e*
# rename -v 's/(Veep_s07e[0-9][0-9])\..*\.mkv/$1.mkv/' *.mkv
# rename -v 's/(.*)s02e([0-9][0-9])\..*\.mkv/$1s02e$2.mkv/' *.mkv
# for f in *.mkv; do mkvmerge -o _$f $f; mv -vf _$f $f; done
# nohup rsync -ahv --no-owner --no-group --no-perms --ignore-existing --progress /data/media/* /media/cdrom &
# nohup rsync -avP /media/cdrom /data/tmp &
