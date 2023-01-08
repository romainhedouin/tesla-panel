./rpi-rgb-led-matrix/examples-api-use/demo --led-no-hardware-pulse ./src/hello2.ppm --led-gpio-mapping=adafruit-hat --led-cols=64 -D 1 &

sleep 4

PID=$!
kill -9 $PID
