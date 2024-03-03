rm -rf ../share_tmp_example.sh
cat <<EOF >../share_tmp_example.sh
rm -rf share_tmp_example
mkdir share_tmp_example
cd share_tmp_example
EOF
find . -type d -exec echo mkdir -p \"{}\" \; >>../share_tmp_example.sh
find . -type f -exec echo touch \"{}\" \; >>../share_tmp_example.sh
cat <<EOF >>../share_tmp_example.sh
echo -n "Dirs created: " && find . -type d | wc -l
echo -n "Files created: " && find . -type f | wc -l
EOF
sed -i -e 's/\$/\\\$/g' ../share_tmp_example.sh
sed -i -e 's/(/\\(/g' ../share_tmp_example.sh
sed -i -e 's/)/\\)/g' ../share_tmp_example.sh
sed -i -e 's/\x27/\\\x27/g' ../share_tmp_example.sh
cat ../share_tmp_example.sh
