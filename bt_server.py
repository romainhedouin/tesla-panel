import bluetooth
import os
import signal
import struct
import time

from rgbmatrix import RGBMatrix, RGBMatrixOptions

pid_file = "/home/pi/bt_server.pid"

COMMAND_IMAGE = 0
COMMAND_KILL = 2
COMMAND_SET_BRIGHTNESS = 3

STATUS_OK = b"\x00"
STATUS_ERROR = b"\x01"

HEADER_FORMAT = ">BI"  # 1 byte command type, 4 bytes big-endian payload length
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

# The matrix and its offscreen canvas are created once and live for the
# whole process - every image update is an atomic SwapOnVSync onto this
# same already-running matrix, never a process kill/respawn. That's what
# makes updates flicker-free: the GPIO refresh loop never stops, so there's
# no gap where nothing is driving the panel.
options = RGBMatrixOptions()
options.rows = 32
options.cols = 64
options.chain_length = 1
options.parallel = 1
options.hardware_mapping = "adafruit-hat"
options.gpio_slowdown = 4
options.disable_hardware_pulsing = True
options.brightness = 100
# The library drops root privileges to the "daemon" user by default right
# after hardware init, which breaks anything after this point that needs to
# write files as root (e.g. bt_server.log under /home/pi). This process is
# meant to run as root for its whole lifetime (systemd already runs it that
# way), so keep the privileges instead of silently losing them mid-startup.
options.drop_privileges = False

matrix = RGBMatrix(options=options)
canvas = matrix.CreateFrameCanvas()


def logger(command):
    print(command)
    with open("/home/pi/bt_server.log", "w") as f:
        f.write(command)
        f.write("\n")


def recv_exact(client_sock, n):
    """Read exactly n bytes, looping over recv() since a single call isn't
    guaranteed to return everything at once. Returns None if the connection
    closes before n bytes arrive."""
    buf = b""
    while len(buf) < n:
        chunk = client_sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def parse_ppm(data):
    """Minimal P6 PPM parser matching exactly what the Android app's
    PpmCodec.encode() produces: 'P6\\n<width> <height>\\n<maxval>\\n' then
    raw width*height RGB triplets. Not a general-purpose PPM parser, but
    the header may still contain a '#'-prefixed comment line - some of the
    bundled assets were exported from GIMP, which adds one - so those must
    be skipped like whitespace rather than parsed as a number."""
    assert data[0:2] == b"P6"
    pos = 2
    values = []
    while len(values) < 3:
        while data[pos] in b" \t\r\n" or data[pos:pos + 1] == b"#":
            if data[pos:pos + 1] == b"#":
                while data[pos] not in b"\r\n":
                    pos += 1
            else:
                pos += 1
        start = pos
        while data[pos] not in b" \t\r\n":
            pos += 1
        values.append(int(data[start:pos]))
    pos += 1  # single whitespace byte separating header from pixel data
    width, height, _maxval = values
    return width, height, data[pos:pos + width * height * 3]


def handle_image(payload):
    global canvas
    width, height, pixels = parse_ppm(payload)
    for y in range(height):
        row = y * width * 3
        for x in range(width):
            i = row + x * 3
            canvas.SetPixel(x, y, pixels[i], pixels[i + 1], pixels[i + 2])
    canvas = matrix.SwapOnVSync(canvas)
    logger("Displayed %dx%d image" % (width, height))


def handle_kill(payload):
    global canvas
    canvas.Clear()
    canvas = matrix.SwapOnVSync(canvas)
    logger("Cleared display")


def handle_set_brightness(payload):
    brightness = payload[0]
    if brightness < 1 or brightness > 100:
        raise ValueError("brightness must be 1-100, got %d" % brightness)
    matrix.brightness = brightness
    logger("Brightness set to %d" % brightness)


HANDLERS = {
    COMMAND_IMAGE: handle_image,
    COMMAND_KILL: handle_kill,
    COMMAND_SET_BRIGHTNESS: handle_set_brightness,
}


def handle_one_command(client_sock):
    """Read and dispatch a single command. Returns False once the client
    has disconnected (nothing more to read), True otherwise."""
    header = recv_exact(client_sock, HEADER_SIZE)
    if header is None:
        return False
    command_type, length = struct.unpack(HEADER_FORMAT, header)

    payload = recv_exact(client_sock, length) if length else b""
    if payload is None:
        return False

    handler = HANDLERS.get(command_type)
    if handler is None:
        logger("[-] Unknown command type: %d" % command_type)
        client_sock.send(STATUS_ERROR)
        return True

    try:
        handler(payload)
        client_sock.send(STATUS_OK)
    except Exception as e:
        logger("[-] Command %d failed: %s" % (command_type, e))
        client_sock.send(STATUS_ERROR)
    return True


if __name__ == '__main__':

    # check if the pid file exists
    if os.path.exists(pid_file):
        # the pid file exists, so read the process ID from the file
        with open(pid_file, 'r') as f:
            pid = int(f.read())

        # try to kill the process
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass

    # At boot, systemd starts this service as soon as its own unit
    # dependencies are satisfied, but that doesn't reliably mean the
    # Bluetooth adapter itself (hci0, brought up by hciuart/bthelper after
    # firmware upload) is ready yet - advertise_service() raises "no
    # advertisable device" for the first second or so. Retrying in-process
    # is more robust than relying on systemd unit ordering here, and it
    # avoids the old behavior of the whole script (and its RGBMatrix
    # instance, expensive to construct) getting killed and restarted by the
    # outer shell loop on every failed attempt.
    uuid = "00001101-0000-1000-8000-00805F9B34FB"
    retry_delay_s = 1
    max_attempts = 30
    for attempt in range(1, max_attempts + 1):
        server_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        server_sock.bind(("", bluetooth.PORT_ANY))
        server_sock.listen(1)
        try:
            bluetooth.advertise_service(server_sock, "My Bluetooth Server",
                            service_id=uuid,
                            service_classes=[uuid, bluetooth.SERIAL_PORT_CLASS],
                            profiles=[bluetooth.SERIAL_PORT_PROFILE])
            break
        except bluetooth.BluetoothError as e:
            server_sock.close()
            if attempt == max_attempts:
                raise
            logger("[-] Bluetooth adapter not ready yet (%s), retrying (%d/%d)..."
                   % (e, attempt, max_attempts))
            time.sleep(retry_delay_s)

    port = server_sock.getsockname()[1]
    logger("[+] Listening for incoming connections on RFCOMM channel " + port.__str__())

    while True:
        client_sock, client_info = server_sock.accept()
        while handle_one_command(client_sock):
            pass
        logger("[+] Disconnected")
        client_sock.close()
