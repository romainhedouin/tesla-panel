# Check every 5 seconds if the server is running, and if not, restart it.
while true; do
  if ! nc -z localhost 8000; then
    echo "Server is not running, restarting..."
    php -S 0.0.0.0:8000 -t /home/pi/
    fi
    sleep 5
done
