"""BlueZ D-Bus Profile1 glue - the modern replacement for PyBluez's
advertise_service(), which stopped working once BlueZ (5.82, current on
Debian 13/trixie) removed the legacy /var/run/sdp socket interface it
depended on for SDP registration (confirmed dead: sdptool fails identically
against the same missing socket).

Registering a profile through org.bluez.ProfileManager1 is what lets BlueZ
generate and serve a real SDP record for us. That's not optional polish -
the Android app connects via createRfcommSocketToServiceRecord(UUID), which
looks up the RFCOMM channel via an actual SDP query at connect time rather
than using a fixed channel number, so it genuinely needs a working SDP
record on the Pi. A hardcoded RFCOMM channel with no SDP record would
satisfy this repo's own bt_client.py test script (which connects to a fixed
channel directly) but not the real app.

Only importable where dbus-python/PyGObject are installed (the Pi, via the
python3-dbus/python3-gi apt packages) - kept separate from protocol.py so
tests can exercise the wire protocol without either.
"""
import socket
import threading
import time

import dbus
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib

SERIAL_PORT_UUID = "00001101-0000-1000-8000-00805f9b34fb"
PROFILE_PATH = "/com/teslaled/profile"
PROFILE_MANAGER_IFACE = "org.bluez.ProfileManager1"


class SerialPortProfile(dbus.service.Object):
    """Exports org.bluez.Profile1 at PROFILE_PATH. BlueZ calls NewConnection
    once per incoming RFCOMM connection, handing over an already-connected
    fd - there's no listen()/accept() on our side at all, BlueZ owns that
    part entirely."""

    def __init__(self, bus, on_connection, logger):
        super().__init__(bus, PROFILE_PATH)
        self.on_connection = on_connection
        self.logger = logger

    @dbus.service.method("org.bluez.Profile1", in_signature="", out_signature="")
    def Release(self):
        self.logger("[bt] Profile released")

    @dbus.service.method("org.bluez.Profile1", in_signature="oha{sv}", out_signature="")
    def NewConnection(self, device, fd, properties):
        # fd is a dbus.types.UnixFd - .take() hands us the raw fd and marks
        # it as ours to close, rather than closed under us when the UnixFd
        # wrapper is garbage collected. socket.socket(fileno=...) then
        # re-derives family/type via getsockopt, same as any other already-
        # connected stream socket.
        sock = socket.socket(fileno=fd.take())
        # BlueZ hands this fd over already set O_NONBLOCK. protocol.py's
        # recv_exact() assumes blocking semantics (it loops on recv() until
        # it has everything) - left non-blocking, the first recv() with no
        # data immediately queued raises BlockingIOError instead of waiting,
        # which is exactly what killed the first end-to-end test against
        # the real Android app.
        sock.setblocking(True)
        self.logger("[bt] New connection from %s" % device)
        # Handled on its own thread so this D-Bus method returns promptly
        # instead of blocking the GLib mainloop (and therefore every other
        # BlueZ callback, including RequestDisconnection) for as long as
        # the client stays connected.
        threading.Thread(target=self.on_connection, args=(sock,), daemon=True).start()

    @dbus.service.method("org.bluez.Profile1", in_signature="o", out_signature="")
    def RequestDisconnection(self, device):
        self.logger("[bt] Disconnection requested for %s" % device)


def register(on_connection, logger, channel=1, retry_delay_s=1, max_attempts=30):
    """Registers the profile and returns (mainloop, profile) - call
    mainloop.run(), and keep `profile` referenced for as long as the
    mainloop runs (nothing else holds a strong reference to it, and a
    garbage-collected dbus.service.Object stops responding on the bus).

    Retries registration since, at boot, systemd may start this service
    before bluetoothd has finished bringing hci0 up - mirrors the retry
    loop the old advertise_service()-based code had for the same reason.
    """
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    profile = SerialPortProfile(bus, on_connection, logger)
    manager = dbus.Interface(bus.get_object("org.bluez", "/org/bluez"),
                              PROFILE_MANAGER_IFACE)

    # Role=server + the well-known Serial Port Profile UUID tells BlueZ to
    # auto-generate a standard SPP SDP record advertising this channel -
    # we don't hand-craft the SDP record ourselves.
    opts = {
        "Name": "TeslaLED",
        "Role": "server",
        "Channel": dbus.UInt16(channel),
        "RequireAuthentication": False,
        "RequireAuthorization": False,
        "AutoConnect": True,
    }

    for attempt in range(1, max_attempts + 1):
        try:
            manager.RegisterProfile(PROFILE_PATH, SERIAL_PORT_UUID, opts)
            break
        except dbus.exceptions.DBusException as e:
            if attempt == max_attempts:
                raise
            logger("[-] Bluetooth adapter not ready yet (%s), retrying (%d/%d)..."
                   % (e, attempt, max_attempts))
            time.sleep(retry_delay_s)

    logger("[+] Registered SDP/RFCOMM profile on channel %d" % channel)
    return GLib.MainLoop(), profile
