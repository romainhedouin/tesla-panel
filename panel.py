"""RGBMatrix hardware wrapper. Only importable on the Pi (needs the
compiled rgbmatrix extension from rpi-rgb-led-matrix), which is why this is
kept separate from protocol.py - tests exercise the protocol against a fake
panel instead of importing this module at all.
"""
from rgbmatrix import RGBMatrix, RGBMatrixOptions

from protocol import COMMAND_IMAGE, COMMAND_KILL, COMMAND_SET_BRIGHTNESS, parse_ppm


class Panel:
    def __init__(self, logger):
        self.logger = logger
        # Created once and live for the whole process - every image update
        # is an atomic SwapOnVSync onto this same already-running matrix,
        # never a process kill/respawn. That's what makes updates
        # flicker-free: the GPIO refresh loop never stops, so there's no
        # gap where nothing is driving the panel.
        options = RGBMatrixOptions()
        options.rows = 32
        options.cols = 64
        options.chain_length = 1
        options.parallel = 1
        options.hardware_mapping = "adafruit-hat"
        options.gpio_slowdown = 4
        options.disable_hardware_pulsing = True
        options.brightness = 100
        # The library drops root privileges to the "daemon" user by default
        # right after hardware init, which breaks anything after this point
        # that needs to write files as root (e.g. bt_server.log under
        # /home/pi). This process is meant to run as root for its whole
        # lifetime (systemd already runs it that way), so keep the
        # privileges instead of silently losing them mid-startup.
        options.drop_privileges = False

        self.matrix = RGBMatrix(options=options)
        self.canvas = self.matrix.CreateFrameCanvas()

    def handle_image(self, payload):
        width, height, pixels = parse_ppm(payload)
        for y in range(height):
            row = y * width * 3
            for x in range(width):
                i = row + x * 3
                self.canvas.SetPixel(x, y, pixels[i], pixels[i + 1], pixels[i + 2])
        self.canvas = self.matrix.SwapOnVSync(self.canvas)
        self.logger("Displayed %dx%d image" % (width, height))

    def handle_kill(self, payload):
        self.canvas.Clear()
        self.canvas = self.matrix.SwapOnVSync(self.canvas)
        self.logger("Cleared display")

    def handle_set_brightness(self, payload):
        brightness = payload[0]
        if brightness < 1 or brightness > 100:
            raise ValueError("brightness must be 1-100, got %d" % brightness)
        self.matrix.brightness = brightness
        self.logger("Brightness set to %d" % brightness)

    def handlers(self):
        return {
            COMMAND_IMAGE: self.handle_image,
            COMMAND_KILL: self.handle_kill,
            COMMAND_SET_BRIGHTNESS: self.handle_set_brightness,
        }
