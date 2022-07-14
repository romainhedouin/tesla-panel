PID_LIST=`pidof ./rpi-rgb-led-matrix/*/*`

## kill all processes
for PID in $PID_LIST
do
    kill -9 $PID
done