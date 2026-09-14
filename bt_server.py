from gi.repository import GLib

import bt_ble
import bt_profile
from panel import Panel
from protocol import handle_one_command


def logger(message):
    print(message)
    with open("/home/pi/bt_server.log", "w") as f:
        f.write(message)
        f.write("\n")


def handle_connection(sock, handlers):
    while handle_one_command(sock, handlers, logger):
        pass
    logger("[+] Disconnected")
    sock.close()


if __name__ == '__main__':

    panel = Panel(logger)
    mainloop, profile = bt_profile.register(
        on_connection=lambda sock: handle_connection(sock, panel.handlers()),
        logger=logger,
    )
    # BLE runs alongside the classic profile above, not instead of it - see
    # bt_ble.py. Registering it has to wait until the mainloop is actually
    # running: BlueZ's RegisterApplication() calls back into our own
    # process (GetManagedObjects) to walk the service/characteristic tree,
    # and nothing services incoming D-Bus calls on our end until
    # mainloop.run() starts pumping events - doing this beforehand
    # deadlocks (confirmed live: RegisterApplication failed with
    # "No object received", and a direct GetManagedObjects call from
    # outside the process timed out completely). GLib.idle_add() runs
    # this once, on the first mainloop iteration, instead.
    ble_state = {}

    def start_ble():
        ble_state["app"], ble_state["advertisement"] = bt_ble.register(
            handlers=panel.handlers(),
            logger=logger,
        )
        return False  # one-shot, not a repeating idle callback

    GLib.idle_add(start_ble)

    logger("[+] Listening for incoming connections via BlueZ SDP/RFCOMM profile and BLE GATT")
    mainloop.run()
