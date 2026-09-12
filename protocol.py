"""Wire protocol for the panel's command channel - hardware- and
transport-agnostic (works over any object with .recv()/.send(), Bluetooth
RFCOMM or otherwise), which is what keeps this importable and unit-testable
without a compiled rgbmatrix extension or a real Bluetooth adapter.

[1 byte command type][4 bytes big-endian payload length][payload]

followed by a single status byte in response (STATUS_OK or STATUS_ERROR).
Matched byte-for-byte by the Android app's BluetoothClient - see README.md.
"""
import struct

COMMAND_IMAGE = 0
COMMAND_KILL = 2
COMMAND_SET_BRIGHTNESS = 3

STATUS_OK = b"\x00"
STATUS_ERROR = b"\x01"

HEADER_FORMAT = ">BI"  # 1 byte command type, 4 bytes big-endian payload length
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)


def recv_exact(sock, n):
    """Read exactly n bytes, looping over recv() since a single call isn't
    guaranteed to return everything at once. Returns None if the connection
    closes before n bytes arrive."""
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
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


def handle_one_command(sock, handlers, logger):
    """Read and dispatch a single command using the given {command_type:
    handler(payload)} mapping. Returns False once the client has
    disconnected (nothing more to read), True otherwise."""
    header = recv_exact(sock, HEADER_SIZE)
    if header is None:
        return False
    command_type, length = struct.unpack(HEADER_FORMAT, header)

    payload = recv_exact(sock, length) if length else b""
    if payload is None:
        return False

    handler = handlers.get(command_type)
    if handler is None:
        logger("[-] Unknown command type: %d" % command_type)
        sock.send(STATUS_ERROR)
        return True

    try:
        handler(payload)
        sock.send(STATUS_OK)
    except Exception as e:
        logger("[-] Command %d failed: %s" % (command_type, e))
        sock.send(STATUS_ERROR)
    return True
