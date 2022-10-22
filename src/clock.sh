./rpi-rgb-led-matrix/examples-api-use/clock -f rpi-rgb-led-matrix/fonts/9x18B.bdf --led-gpio-mapping=adafruit-hat --led-cols=64 &

sleep 3

PID=$!
kill -9 $PID
