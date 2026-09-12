import os
import signal

import bt_profile
from panel import Panel
from protocol import handle_one_command

pid_file = "/home/pi/bt_server.pid"


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

    panel = Panel(logger)
    mainloop, profile = bt_profile.register(
        on_connection=lambda sock: handle_connection(sock, panel.handlers()),
        logger=logger,
    )
    logger("[+] Listening for incoming connections via BlueZ SDP/RFCOMM profile")
    mainloop.run()
