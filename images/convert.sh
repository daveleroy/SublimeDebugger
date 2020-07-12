#!/bin/bash

mkdir "magick_cache"

for f in base/*.png
do
	filename=$(basename "${f}")
	filename_no_ext="${filename%.*}"
	file_negated_temp="magick_cache/${filename_no_ext}_negated.png"
	file_blur_temp="magick_cache/${filename_no_ext}_blur.png"

	# temp background blurred image
	magick convert -alpha set -background none -channel A -evaluate multiply 0.5 +channel -resize 32x32 -blur 10x10 "base/${filename}" "${file_blur_temp}"
	# temp negated image
	magick convert -resize 32x32 -channel RGB -negate "base/${filename}" "${file_negated_temp}"

	# generate dark/light image + blurred (always dark) background
	magick convert -resize 32x32 "${file_blur_temp}" "base/${filename}" -composite "dark/"${filename_no_ext}".png"
	magick convert -resize 32x32 "${file_blur_temp}" "${file_negated_temp}" -composite "light/"${filename_no_ext}".png"

	# generate dark/lighht disabled variants
	magick convert -alpha set -background none -channel A -evaluate multiply 0.15 +channel -resize 32x32 "${file_blur_temp}" "base/${filename}" -composite "dark/"${filename_no_ext}"_disabled.png"
	magick convert -alpha set -background none -channel A -evaluate multiply 0.15 +channel -resize 32x32 "${file_blur_temp}" "${file_negated_temp}" -composite "light/"${filename_no_ext}"_disabled.png"

done
rm -rf "magick_cache"
