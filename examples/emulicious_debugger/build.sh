rm -r bin/
mkdir bin/
../bin/evscript -d - -o bin/script.asm script.evs | cat config.evd - > bin/test.evd
rgbgfx -c embedded -o bin/font.2bpp font.png
rgbasm -h -o bin/test.o test.asm
rgblink -n bin/test.sym -m bin/test.map -o bin/test.gb bin/test.o
rgbfix -flhg bin/test.gb
