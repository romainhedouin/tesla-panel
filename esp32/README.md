# ESP32 firmware (in progress)

Alternative to the Raspberry Pi, targeting the [HUB75 adapter for
ESP32-DevKitC V4 / ESP32-S3 DevKitC-1](https://www.amazon.fr/dp/B0FVGCF1RW).
Written and compile-verified with [PlatformIO](https://platformio.org/)
(`pip install platformio`) without the physical board in hand - `pio run`
only compiles/links, it doesn't need real hardware. **Nothing here has
been flashed to or tested on real hardware yet.**

## Why two environments

That adapter board is designed to take either dev board, and the two are
not interchangeable for our purposes: the original ESP32 has classic
Bluetooth (BR/EDR), the S3 dropped it entirely (BLE only). That's a
protocol-level fork, not a config option:

- **`esp32-classic`** (`src/main_classic.cpp`) - original ESP32. Uses
  Arduino's `BluetoothSerial` for RFCOMM/SPP, which registers the same
  standard SPP UUID (`00001101-...`) the Android app already targets via
  `createRfcommSocketToServiceRecord()` - no app-side changes needed to
  point it at this instead of the Pi.
- **`esp32-s3-ble`** (`src/main_ble.cpp`) - ESP32-S3. No classic Bluetooth
  radio exists on this chip, so this speaks BLE GATT instead: a custom
  service with a write characteristic (phone → board) and a notify
  characteristic (board → phone). **The Android app has no BLE client yet
  - this firmware alone doesn't make the S3 path usable end to end.**

`build_src_filter` in `platformio.ini` picks the right entry point per
environment; everything else (`protocol.h`, `panel.h`) is shared.

## Structure

- `protocol.h` - wire protocol, mirrors `protocol.py` at the repo root
  byte-for-byte (same command values, same length-prefixed framing, same
  response shape, same PPM parser). Transport-agnostic: only parses bytes
  already in a buffer, never touches Bluetooth directly.
- `panel.h` - HUB75 driving wrapper, mirrors `panel.py`'s role, built on
  [ESP32-HUB75-MatrixPanel-DMA](https://github.com/mrcodetastic/ESP32-HUB75-MatrixPanel-DMA)
  (confirmed to support ESP32/S2/S3). Double-buffered
  (`SwapOnVSync`-equivalent) for the same flicker-free updates as the Pi.
- `main_classic.cpp` / `main_ble.cpp` - the two entry points above.

## What's still unverified / unknown

- **Pin mapping**: left at the library's defaults - the adapter board's
  actual wiring isn't documented anywhere I could check without the
  hardware. Expect to adjust the `HUB75_I2S_CFG` in `panel.h` once it
  arrives.
- **Everything BLE-side is unverified beyond "it compiles"**: MTU
  negotiation, chunked reassembly under real radio conditions, actual
  throughput for a 6KB frame split into GATT writes - all need a real S3
  board and a real BLE central to know if the design holds up.
- **The Android BLE client doesn't exist yet** - see the custom UUIDs
  above; a separate, real piece of work.

## Building

```
cd esp32
pio run -e esp32-classic   # or -e esp32-s3-ble
pio run -e esp32-classic -t upload   # once you actually have the board wired up
```
