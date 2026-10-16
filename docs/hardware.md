# Hardware

## Initial proposal

- ESP32.
- Microphone MAX4466.
- USB 5 V power supply.
- Dim LED for local alerts.

## To confirm

- The actual ESP32 model/version and microphone.
- Voltage compatibility, signal levels, and power supply.
- ADC and LED pins, wiring, enclosure, and device placement.
- Sampling rate, microphone amplification/gain, and saturation threshold.

There is no universal wiring diagram for every ESP32 variant; a diagram will be produced only after the specific hardware is confirmed.

## Configuration to record

Record the board/microphone versions, pins, firmware, sampling rate, gain, P2P calculation, alert threshold, and test-environment conditions. Do not commit real Wi-Fi SSIDs or passwords to Git.

## Test plan

1. Verify safe power and ADC signals with the confirmed hardware.
2. Record P2P in a quiet environment and with an appropriate reference signal.
3. Test saturation, the LED, Wi-Fi/reconnection, and 10-second transmissions.
4. Run a continuous overnight test once the pipeline is ready.
