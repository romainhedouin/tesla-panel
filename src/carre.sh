./rpi-rgb-led-matrix/examples-api-use/demo -D 0 --led-no-hardware-pulse --led-gpio-mapping=adafruit-hat --led-cols=64 &

sleep 4

PID=`echo $!`
kill -9 $PID
