"""Shared retry tuning for registering with BlueZ at boot - systemd may
start teslabot before bluetoothd has finished bringing hci0 up, so both
bt_profile.py's classic SPP profile and bt_ble.py's GATT application retry
their registration call against BlueZ. Kept in one place because the two
loops need the same delay/attempt budget, even though the loops themselves
can't be merged: bt_profile.register() runs before the GLib mainloop starts
(so a blocking time.sleep() retry is fine), while bt_ble.register() runs
after (where blocking would freeze the mainloop, so it reschedules itself
via GLib.timeout_add() instead).
"""
RETRY_DELAY_S = 1
MAX_ATTEMPTS = 30


def not_ready_message(what, error, attempt, max_attempts):
    return "[-] %s not ready yet (%s), retrying (%d/%d)..." % (what, error, attempt, max_attempts)
