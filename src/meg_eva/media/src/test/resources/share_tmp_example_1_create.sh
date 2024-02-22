rm -rf ../share_tmp_example_1.sh
cat <<EOF >../share_tmp_example_1.sh
rm -rf share_tmp_example_1
mkdir share_tmp_example_1
cd share_tmp_example_1
EOF
find . -type d -exec echo mkdir -p \"{}\" \; >>../share_tmp_example_1.sh
find . -type f -exec echo touch \"{}\" \; >>../share_tmp_example_1.sh
cat <<EOF >>../share_tmp_example_1.sh
echo -n "Dirs created: " && find . -type d | wc -l
echo -n "Files created: " && find . -type f | wc -l
EOF
sed -i -e 's/\$/\\\$/g' ../share_tmp_example_1.sh
sed -i -e 's/(/\\(/g' ../share_tmp_example_1.sh
sed -i -e 's/)/\\)/g' ../share_tmp_example_1.sh
sed -i -e 's/\x27/\\\x27/g' ../share_tmp_example_1.sh
cat ../share_tmp_example_1.sh
