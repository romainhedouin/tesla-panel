// Entry point for the ESP32-S3 (BLE only - no classic Bluetooth radio at
// all on this chip, so BluetoothSerial/SPP isn't an option here). Speaks
// the same logical wire protocol as the Pi/classic-ESP32 (protocol.h), but
// framed differently: BLE GATT writes/notifies are capped by the
// negotiated MTU (a handful of hundred bytes at best), while a 64x32 PPM
// image is ~6.2KB - the phone must split a command across several
// characteristic writes, and this reassembles them here before dispatching.
//
// Custom GATT service (no standard profile fits this - unlike classic SPP,
// BLE has no generic "serial port" analog):
//   Service:               c9af0000-1a1a-4e7e-9a1e-4b1e2f6a9c00
//   Command characteristic c9af0000-1a1a-4e7e-9a1e-4b1e2f6a9c01 (write)  - phone -> board
//   Response characteristic c9af0000-1a1a-4e7e-9a1e-4b1e2f6a9c02 (notify) - board -> phone
// The Android app needs a BLE client implementing this service to talk to
// this firmware variant - a separate piece of work from this firmware.
#include <Arduino.h>
#include <BLE2902.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>

#include <vector>

#include "panel.h"
#include "protocol.h"

namespace {

constexpr char kServiceUuid[] = "c9af0000-1a1a-4e7e-9a1e-4b1e2f6a9c00";
constexpr char kCommandCharUuid[] = "c9af0000-1a1a-4e7e-9a1e-4b1e2f6a9c01";
constexpr char kResponseCharUuid[] = "c9af0000-1a1a-4e7e-9a1e-4b1e2f6a9c02";

Panel *gPanel;
BLEServer *gServer;
BLECharacteristic *gResponseChar;

// Growable reassembly buffer for the command currently being received -
// BLE writes arrive in MTU-sized chunks (a fraction of a 6KB image frame),
// so a full command is spread across several onWrite() calls. Reset once
// a full command has been dispatched, or when a new connection begins.
std::vector<uint8_t> gBuffer;

void sendResponse(uint8_t status, const String &message) {
  uint8_t header[protocol::RESPONSE_HEADER_SIZE];
  header[0] = status;
  protocol::writeU32BE(header + 1, message.length());
  // Response is always small (a short status message) - well under any
  // negotiated MTU, so unlike the command direction this never needs to be
  // split across multiple notifications.
  std::vector<uint8_t> response(header, header + sizeof(header));
  response.insert(response.end(), message.begin(), message.end());
  gResponseChar->setValue(response.data(), response.size());
  gResponseChar->notify();
}

// Dispatches the fully-reassembled command in gBuffer, mirroring
// handle_one_command() in protocol.py, then clears it for the next one.
void dispatchBufferedCommand() {
  protocol::ParsedHeader parsed = protocol::parseHeader(gBuffer.data());
  const uint8_t *payload = gBuffer.data() + protocol::HEADER_SIZE;

  String error;
  bool ok;
  switch (parsed.commandType) {
    case protocol::COMMAND_IMAGE:
      ok = gPanel->handleImage(payload, parsed.length, &error);
      break;
    case protocol::COMMAND_KILL:
      ok = gPanel->handleKill(&error);
      break;
    case protocol::COMMAND_SET_BRIGHTNESS:
      ok = gPanel->handleSetBrightness(payload, parsed.length, &error);
      break;
    default:
      ok = false;
      error = "Unknown command type: " + String(parsed.commandType);
      break;
  }

  if (ok) {
    sendResponse(protocol::STATUS_OK, "");
  } else {
    Serial.println("[-] Command " + String(parsed.commandType) + " failed: " + error);
    sendResponse(protocol::STATUS_ERROR, error);
  }
  gBuffer.clear();
}

class CommandCallbacks : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic *characteristic) override {
    uint8_t *data = characteristic->getData();
    size_t length = characteristic->getLength();
    gBuffer.insert(gBuffer.end(), data, data + length);

    if (gBuffer.size() < protocol::HEADER_SIZE) {
      return;  // haven't even got the header yet
    }
    protocol::ParsedHeader parsed = protocol::parseHeader(gBuffer.data());
    if (parsed.length > protocol::MAX_PAYLOAD_SIZE) {
      Serial.printf("[-] Payload length %u exceeds max %u (desynced stream?) - resetting\n",
                    (unsigned)parsed.length, (unsigned)protocol::MAX_PAYLOAD_SIZE);
      gBuffer.clear();
      return;
    }
    if (gBuffer.size() >= protocol::HEADER_SIZE + parsed.length) {
      dispatchBufferedCommand();
    }
  }
};

class ServerCallbacks : public BLEServerCallbacks {
  void onConnect(BLEServer *server) override {
    Serial.println("[+] BLE client connected");
    gBuffer.clear();
  }

  void onDisconnect(BLEServer *server) override {
    Serial.println("[+] BLE client disconnected");
    gBuffer.clear();
    // Arduino BLE doesn't resume advertising on its own after a disconnect.
    server->startAdvertising();
  }
};

}  // namespace

void setup() {
  Serial.begin(115200);
  gPanel = new Panel();
  gBuffer.reserve(protocol::HEADER_SIZE + 4096);

  BLEDevice::init("teslapi-esp32-ble");
  BLEDevice::setMTU(517);  // request the max - fewer chunks per image frame

  gServer = BLEDevice::createServer();
  gServer->setCallbacks(new ServerCallbacks());

  BLEService *service = gServer->createService(kServiceUuid);

  BLECharacteristic *commandChar = service->createCharacteristic(
      kCommandCharUuid, BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR);
  commandChar->setCallbacks(new CommandCallbacks());

  gResponseChar = service->createCharacteristic(kResponseCharUuid, BLECharacteristic::PROPERTY_NOTIFY);
  gResponseChar->addDescriptor(new BLE2902());  // CCCD - required for the client to enable notifications

  service->start();
  gServer->getAdvertising()->addServiceUUID(kServiceUuid);
  gServer->getAdvertising()->start();
  Serial.println("[+] BLE GATT server started as \"teslapi-esp32-ble\"");
}

void loop() {
  delay(100);  // everything happens in BLE callbacks - nothing to poll here
}
