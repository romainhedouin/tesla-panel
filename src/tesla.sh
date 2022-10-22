./rpi-rgb-led-matrix/examples-api-use/demo --led-no-hardware-pulse ./src/tesla.ppm --led-gpio-mapping=adafruit-hat --led-cols=64 -D 1 &

sleep 4

PID=`echo $!`
kill -9 $PID

./rpi-rgb-led-matrix/examples-api-use/demo --led-no-hardware-pulse ./src/red_heart.ppm --led-gpio-mapping=adafruit-hat --led-cols=64 -D 1 &

sleep 1

PID=`echo $!`
kill -9 $PID
