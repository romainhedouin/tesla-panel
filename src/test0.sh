./rpi-rgb-led-matrix/examples-api-use/demo -D 0 --led-gpio-mapping=adafruit-hat --led-cols=64

PID=`echo $!`
kill -9 $PID
