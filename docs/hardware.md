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

## Firmware example (unconfirmed hardware)

The provisional `esp32dev_example` compile target assumes a classic dual-core
ESP32, 12-bit ADC1 GPIO34, `ADC_11db`, best-effort 500 Hz sampling, 50 ms P2P
windows, and rail clipping limits 0/4095. These are sanitized development
defaults, not measured settings. Gain and supply remain unconfirmed. Check
board-specific ADC voltage compatibility before wiring/enabling sampling.
Follow [firmware instructions](../firmware/README.md) for local configuration.

## Configuration to record

Record the board/microphone versions, pins, firmware, sampling rate, gain, P2P calculation, alert threshold, and test-environment conditions. Do not commit real Wi-Fi SSIDs or passwords to Git.

## Test plan

1. Verify safe power and ADC signals with the confirmed hardware.
2. Record P2P in a quiet environment and with an appropriate reference signal.
3. For Sprint 1, test saturation, Wi-Fi/reconnection, and 10-second transmissions.
   LED acceptance belongs to the later alert work.
4. Run a continuous overnight test once the pipeline is ready.

Follow the [producer acceptance procedure](producer-acceptance.md) to record
actual hardware settings, sound-response observations, network-fault sampling,
and API receipt evidence for issue #3.
