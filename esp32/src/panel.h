// HUB75 hardware wrapper - mirrors panel.py's role and structure (a Panel
// class exposing handleImage/handleKill/handleSetBrightness, each raising/
// returning an error message on invalid input rather than crashing).
//
// Pin mapping: left at the library's defaults (see HUB75_I2S_CFG in
// ESP32-HUB75-MatrixPanel-I2S-DMA.h) since the exact wiring of the actual
// adapter board isn't known yet - no hardware to verify against. Expect to
// revisit PANEL_R1_PIN etc. below once the board arrives.
#pragma once

#include <ESP32-HUB75-MatrixPanel-I2S-DMA.h>

#include "protocol.h"

class Panel {
 public:
  Panel() {
    HUB75_I2S_CFG cfg(64, 32, 1);  // width, height, chain length - matches panel.py
    cfg.double_buff = true;        // flicker-free: draw to the back buffer, flip on swap
    display_ = new MatrixPanel_I2S_DMA(cfg);
    display_->begin();
    display_->setBrightness8(255);
    display_->clearScreen();
    display_->flipDMABuffer();
  }

  // Returns true on success. On failure, sets *error to a human-readable
  // reason and leaves the panel showing whatever it last successfully
  // displayed - mirrors handle_image()/parse_ppm() in protocol.py/panel.py.
  bool handleImage(const uint8_t *payload, size_t length, String *error) {
    protocol::Ppm ppm;
    if (!protocol::parsePpm(payload, length, &ppm, error)) {
      return false;
    }
    for (int y = 0; y < ppm.height; y++) {
      size_t row = size_t(y) * ppm.width * 3;
      for (int x = 0; x < ppm.width; x++) {
        size_t i = row + size_t(x) * 3;
        display_->drawPixelRGB888(x, y, ppm.pixels[i], ppm.pixels[i + 1], ppm.pixels[i + 2]);
      }
    }
    display_->flipDMABuffer();
    return true;
  }

  bool handleKill(String *error) {
    display_->clearScreen();
    display_->flipDMABuffer();
    return true;
  }

  bool handleSetBrightness(const uint8_t *payload, size_t length, String *error) {
    if (length < 1) {
      *error = "brightness payload empty";
      return false;
    }
    int brightness = payload[0];
    if (brightness < 1 || brightness > 100) {
      *error = "brightness must be 1-100, got " + String(brightness);
      return false;
    }
    // Wire protocol carries 1-100 (matches the Android app/Pi side); the
    // library wants an 8-bit 0-255 value.
    display_->setBrightness8(uint8_t((brightness * 255 + 50) / 100));
    return true;
  }

 private:
  MatrixPanel_I2S_DMA *display_;
};
