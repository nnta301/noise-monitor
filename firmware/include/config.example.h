#pragma once

// Copy to config.local.h (ignored). Confirm hardware before setting this true.
#ifndef NOISE_HARDWARE_CONFIRMED
#define NOISE_HARDWARE_CONFIRMED false
#endif
#define NOISE_WIFI_SSID ""
#define NOISE_WIFI_PASSWORD ""
#define NOISE_ENDPOINT "http://192.0.2.1:8000/api/v1/telemetry"
#define NOISE_DEVICE_KEY ""
#define NOISE_TIMEZONE "Asia/Ho_Chi_Minh"
// Example for classic ESP32 only: ADC1 remains available with Wi-Fi active.
#define NOISE_ADC_PIN 34
#define NOISE_SAMPLE_PERIOD_US 2000
#define NOISE_CLIP_LOW 0
#define NOISE_CLIP_HIGH 4095
