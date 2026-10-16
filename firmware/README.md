# Firmware

This directory will contain the ESP32 firmware: microphone sampling, per-second P2P feature calculation, telemetry packaging, and transmission every 10 seconds. The firmware does not store or transmit raw audio.

There is no source code, PlatformIO configuration, or pin map yet. The board, microphone, ADC pin, sampling rate, and offline queue policy must be confirmed before implementation.
