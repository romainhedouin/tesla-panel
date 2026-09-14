"""BLE GATT peripheral - the transport a future ESP32-S3 will use (no
classic Bluetooth radio on that chip at all), registered here on the Pi
too so the Android app's BleTransport can be built and verified against
real hardware before the ESP32-S3 exists. Runs alongside bt_profile.py's
classic SPP profile, not instead of it - teslabot accepts connections on
both simultaneously. Matches esp32/src/main_ble.cpp's UUIDs and framing
exactly, so the same Android code talks to either.

BlueZ's GATT server lives entirely on D-Bus (org.bluez.GattManager1/
GattService1/GattCharacteristic1) - there's no socket to read/write the
way classic RFCOMM gives you. A write from the client arrives as a
WriteValue() D-Bus method call; a response is delivered by updating the
response characteristic's Value and emitting PropertiesChanged, which
BlueZ turns into a real GATT notification for subscribed clients.
"""
import struct

import dbus
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib

from bt_retry import MAX_ATTEMPTS, RETRY_DELAY_S, not_ready_message
from protocol import (
    HEADER_FORMAT,
    HEADER_SIZE,
    MAX_PAYLOAD_SIZE,
    STATUS_ERROR,
    STATUS_OK,
)

BLUEZ_SERVICE_NAME = "org.bluez"
ADAPTER_PATH = "/org/bluez/hci0"
GATT_MANAGER_IFACE = "org.bluez.GattManager1"
GATT_SERVICE_IFACE = "org.bluez.GattService1"
GATT_CHRC_IFACE = "org.bluez.GattCharacteristic1"
LE_ADVERTISING_MANAGER_IFACE = "org.bluez.LEAdvertisingManager1"
LE_ADVERTISEMENT_IFACE = "org.bluez.LEAdvertisement1"
DBUS_OM_IFACE = "org.freedesktop.DBus.ObjectManager"
DBUS_PROP_IFACE = "org.freedesktop.DBus.Properties"

# Same custom UUIDs as esp32/src/main_ble.cpp - not a standard profile,
# BLE has no generic "serial port" analog the way classic Bluetooth does.
SERVICE_UUID = "c9af0000-1a1a-4e7e-9a1e-4b1e2f6a9c00"
COMMAND_CHAR_UUID = "c9af0000-1a1a-4e7e-9a1e-4b1e2f6a9c01"
RESPONSE_CHAR_UUID = "c9af0000-1a1a-4e7e-9a1e-4b1e2f6a9c02"


class Characteristic(dbus.service.Object):
    def __init__(self, bus, index, uuid, flags, service):
        self.path = service.path + "/char" + str(index)
        self.uuid = uuid
        self.service = service
        self.flags = flags
        self.notifying = False
        self.value = []
        dbus.service.Object.__init__(self, bus, self.path)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def get_properties(self):
        return {
            GATT_CHRC_IFACE: {
                "Service": self.service.get_path(),
                "UUID": self.uuid,
                "Flags": self.flags,
            }
        }

    @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != GATT_CHRC_IFACE:
            raise dbus.exceptions.DBusException(
                "org.bluez.Error.InvalidArguments", "no such interface")
        return self.get_properties()[GATT_CHRC_IFACE]

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="a{sv}", out_signature="ay")
    def ReadValue(self, options):
        return self.value

    @dbus.service.method(GATT_CHRC_IFACE)
    def StartNotify(self):
        self.notifying = True

    @dbus.service.method(GATT_CHRC_IFACE)
    def StopNotify(self):
        self.notifying = False

    @dbus.service.signal(DBUS_PROP_IFACE, signature="sa{sv}as")
    def PropertiesChanged(self, interface, changed, invalidated):
        pass

    def notify(self, value_bytes):
        if not self.notifying:
            return
        self.value = dbus.Array(value_bytes, signature="y")
        self.PropertiesChanged(GATT_CHRC_IFACE, {"Value": self.value}, [])


class CommandCharacteristic(Characteristic):
    """Phone -> Pi. Reassembles a command across multiple BLE writes (a
    ~6.2KB image frame is far bigger than any negotiated MTU), mirroring
    the accumulate-then-dispatch logic in main_ble.cpp's onWrite() - same
    framing, just triggered by WriteValue() calls instead of onWrite()."""

    def __init__(self, bus, index, service, handlers, logger, response_char):
        Characteristic.__init__(self, bus, index, COMMAND_CHAR_UUID,
                                 ["write", "write-without-response"], service)
        self.handlers = handlers
        self.logger = logger
        self.response_char = response_char
        self.buffer = bytearray()

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="aya{sv}")
    def WriteValue(self, value, options):
        self.buffer.extend(bytes(value))
        if len(self.buffer) < HEADER_SIZE:
            return
        command_type, length = struct.unpack(HEADER_FORMAT, bytes(self.buffer[:HEADER_SIZE]))
        if length > MAX_PAYLOAD_SIZE:
            self.logger("[-] BLE payload length %d exceeds max %d (desynced stream?) - resetting"
                        % (length, MAX_PAYLOAD_SIZE))
            self.buffer = bytearray()
            return
        if len(self.buffer) < HEADER_SIZE + length:
            return  # more chunks still to come for this command

        payload = bytes(self.buffer[HEADER_SIZE:HEADER_SIZE + length])
        self.buffer = bytearray()

        handler = self.handlers.get(command_type)
        if handler is None:
            message = "Unknown command type: %d" % command_type
            self.logger("[-] " + message)
            self.response_char.notify_response(STATUS_ERROR, message)
            return
        try:
            handler(payload)
            self.response_char.notify_response(STATUS_OK, "")
        except Exception as e:
            message = str(e) or type(e).__name__
            self.logger("[-] Command %d failed: %s" % (command_type, message))
            self.response_char.notify_response(STATUS_ERROR, message)


class ResponseCharacteristic(Characteristic):
    """Pi -> phone. Always a single notification - status responses are
    short (a status byte + a short message), never a full image, so unlike
    the command direction this never needs reassembly."""

    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, RESPONSE_CHAR_UUID, ["notify"], service)

    def notify_response(self, status, message):
        encoded = message.encode("utf-8")
        header = struct.pack(">BI", status, len(encoded))
        self.notify(list(header) + list(encoded))


class PanelService(dbus.service.Object):
    PATH = "/com/teslaled/ble/service0"

    def __init__(self, bus, handlers, logger):
        self.path = self.PATH
        dbus.service.Object.__init__(self, bus, self.path)
        response_char = ResponseCharacteristic(bus, 1, self)
        command_char = CommandCharacteristic(bus, 0, self, handlers, logger, response_char)
        self.characteristics = [command_char, response_char]

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def get_properties(self):
        return {
            GATT_SERVICE_IFACE: {
                "UUID": SERVICE_UUID,
                "Primary": True,
                "Characteristics": dbus.Array(
                    [c.get_path() for c in self.characteristics], signature="o"),
            }
        }

    @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != GATT_SERVICE_IFACE:
            raise dbus.exceptions.DBusException(
                "org.bluez.Error.InvalidArguments", "no such interface")
        return self.get_properties()[GATT_SERVICE_IFACE]


class Application(dbus.service.Object):
    """Root object BlueZ walks (via GetManagedObjects) to discover the
    whole service/characteristic tree in one RegisterApplication() call."""

    PATH = "/com/teslaled/ble"

    def __init__(self, bus, handlers, logger):
        dbus.service.Object.__init__(self, bus, self.PATH)
        self.service = PanelService(bus, handlers, logger)

    def get_path(self):
        return dbus.ObjectPath(self.PATH)

    @dbus.service.method(DBUS_OM_IFACE, out_signature="a{oa{sa{sv}}}")
    def GetManagedObjects(self):
        response = {self.service.get_path(): self.service.get_properties()}
        for chrc in self.service.characteristics:
            response[chrc.get_path()] = chrc.get_properties()
        return response


class Advertisement(dbus.service.Object):
    PATH = "/com/teslaled/ble/advertisement0"

    def __init__(self, bus):
        dbus.service.Object.__init__(self, bus, self.PATH)

    def get_path(self):
        return dbus.ObjectPath(self.PATH)

    def get_properties(self):
        return {
            LE_ADVERTISEMENT_IFACE: {
                "Type": "peripheral",
                "ServiceUUIDs": dbus.Array([SERVICE_UUID], signature="s"),
                "LocalName": "teslapi-ble",
            }
        }

    @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != LE_ADVERTISEMENT_IFACE:
            raise dbus.exceptions.DBusException(
                "org.bluez.Error.InvalidArguments", "no such interface")
        return self.get_properties()[LE_ADVERTISEMENT_IFACE]

    @dbus.service.method(LE_ADVERTISEMENT_IFACE)
    def Release(self):
        pass


def register(handlers, logger, retry_delay_s=RETRY_DELAY_S, max_attempts=MAX_ATTEMPTS):
    """Registers the GATT application and starts advertising. Returns
    (app, advertisement) immediately - keep both referenced for as long as
    the process runs, same reason as bt_profile.register()'s `profile`
    return value: a garbage-collected dbus.service.Object stops responding
    on the bus. Actual registration success/failure is only known later,
    reported via `logger`.

    RegisterApplication() MUST be called asynchronously (reply_handler/
    error_handler), not as a synchronous/blocking call - confirmed live: a
    synchronous call here deadlocks, because BlueZ calls back into our own
    process (GetManagedObjects, to walk the service/characteristic tree)
    as part of handling it, and that reentrant call can only be serviced
    by our side while the GLib mainloop is actually free to process
    incoming requests, not while it's itself blocked waiting on this call's
    reply. A blocking retry loop (time.sleep()) has the same problem one
    level up, so retries are scheduled via GLib.timeout_add() instead.

    Doesn't create or return its own mainloop - bt_profile.register()'s
    GLib.MainLoop already services every D-Bus object on this connection,
    classic profile and this GATT app alike, once bt_server.py calls
    .run() on it.
    """
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    gatt_manager = dbus.Interface(
        bus.get_object(BLUEZ_SERVICE_NAME, ADAPTER_PATH), GATT_MANAGER_IFACE)
    ad_manager = dbus.Interface(
        bus.get_object(BLUEZ_SERVICE_NAME, ADAPTER_PATH), LE_ADVERTISING_MANAGER_IFACE)

    app = Application(bus, handlers, logger)
    advertisement = Advertisement(bus)
    state = {"attempt": 0}

    def on_app_registered():
        logger("[+] BLE GATT server registered - starting advertisement...")
        ad_manager.RegisterAdvertisement(
            advertisement.get_path(), {},
            reply_handler=lambda: logger("[+] BLE advertising as \"teslapi-ble\""),
            error_handler=lambda e: logger("[-] BLE advertisement registration failed: %s" % e))

    def try_register():
        state["attempt"] += 1

        def on_error(error):
            if state["attempt"] >= max_attempts:
                logger("[-] BLE GATT app registration failed permanently: %s" % error)
                return
            logger(not_ready_message("BLE adapter", error, state["attempt"], max_attempts))
            GLib.timeout_add(int(retry_delay_s * 1000), try_register)

        gatt_manager.RegisterApplication(
            app.get_path(), {}, reply_handler=on_app_registered, error_handler=on_error)
        return False  # GLib.timeout_add: one-shot, try_register() re-schedules itself on error

    try_register()
    return app, advertisement
