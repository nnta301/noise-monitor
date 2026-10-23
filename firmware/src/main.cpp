#include <Arduino.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <WiFi.h>
#include <esp_system.h>
#include <esp_timer.h>
#include "noise_telemetry.h"
#if __has_include("config.local.h")
#include "config.local.h"
#else
#include "config.example.h"
#endif

static_assert(NOISE_SAMPLE_PERIOD_US >= 100 && NOISE_SAMPLE_PERIOD_US <= 10000,
              "Choose a sampling period between 100 and 10000 us");
static_assert(NOISE_CLIP_LOW >= 0 && NOISE_CLIP_HIGH <= 4095 &&
              NOISE_CLIP_LOW < NOISE_CLIP_HIGH, "Invalid clipping thresholds");

QueueHandle_t batches;
char bootId[37];
String deviceId;

void upload(void*) {
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  uint64_t reconnectAt = 0;
  noise::Batch batch;
  for (;;) {
    if (WiFi.status() != WL_CONNECTED && esp_timer_get_time() >= reconnectAt) {
      WiFi.begin(NOISE_WIFI_SSID, NOISE_WIFI_PASSWORD);
      reconnectAt = esp_timer_get_time() + 10000000ULL;
    }
    if (xQueueReceive(batches, &batch, pdMS_TO_TICKS(100)) != pdTRUE) continue;
    if (WiFi.status() != WL_CONNECTED) {
      Serial.printf("network offline; dropped sequence=%llu\n", batch.sequence);
      continue;
    }
    // This initial transport is explicitly for a local HTTP test network.
    // HTTPS needs certificate provisioning before Internet deployment.
    String endpoint(NOISE_ENDPOINT);
    if (!endpoint.startsWith("http://")) {
      Serial.println("network configuration error: local HTTP endpoint required");
      continue;
    }
    WiFiClient client;
    HTTPClient http;
    http.useHTTP10(true);
    http.setConnectTimeout(2000);
    http.setTimeout(2000);
    http.setFollowRedirects(HTTPC_DISABLE_FOLLOW_REDIRECTS);
    if (!http.begin(client, endpoint)) {
      Serial.println("network initialization failure");
      continue;
    }
    http.addHeader("Content-Type", "application/json");
    if (strlen(NOISE_DEVICE_KEY)) http.addHeader("X-Device-Key", NOISE_DEVICE_KEY);
    String body;
    StaticJsonDocument<2048> json;
    noise::fillTelemetry(json, batch, deviceId.c_str(), bootId, NOISE_TIMEZONE);
    if (json.overflowed() || serializeJson(json, body) == 0) {
      Serial.printf("network serialization failure sequence=%llu\n", batch.sequence);
      http.end();
      continue;
    }
    const int status = http.POST(body);
    bool acknowledged = false;
    if (status == 202) {
      StaticJsonDocument<512> response;
      // Parse from the bounded response document without retaining the body.
      const auto error = deserializeJson(response, http.getStream());
      acknowledged = !error && noise::matchesAcknowledgement(
          response.as<JsonVariantConst>(), batch, deviceId.c_str(), bootId);
    }
    Serial.printf("network sequence=%llu http_status=%d acknowledged=%s\n",
                  batch.sequence, status, acknowledged ? "true" : "false");
    http.end();
  }
}

void sample(void*) {
  noise::Batch batch;
  uint64_t windowStart = esp_timer_get_time();
  batch.measuredMs = windowStart / 1000;
  uint64_t nextSample = windowStart;
  noise::Second second;
  unsigned window = 0, slot = 0;
  for (;;) {
    const uint64_t now = esp_timer_get_time();
    // Close every elapsed slot before taking a new reading. Missed windows
    // remain missing instead of compressing a scheduling pause into the past.
    while (now >= windowStart + noise::kWindowUs) {
      second.finishWindow();
      windowStart += noise::kWindowUs;
      if (++window == noise::kWindows) {
        auto feature = second.finish();
        batch.features[slot++] = feature;
        Serial.printf("sensor samples=%u invalid=%u clipped=%u windows=%u median=%d peak=%d flag=%s\n",
                      feature.samples, feature.invalid, feature.clipped, feature.windows,
                      feature.median, feature.peak, feature.flag);
        second = noise::Second{};
        window = 0;
        if (slot == noise::kBatchSeconds) {
          if (xQueueSend(batches, &batch, 0) != pdTRUE)
            Serial.printf("network queue full; dropped sequence=%llu\n", batch.sequence);
          ++batch.sequence;
          batch.measuredMs = windowStart / 1000;
          slot = 0;
        }
      }
    }
    if (now >= nextSample) {
      second.sample(analogRead(NOISE_ADC_PIN), NOISE_CLIP_LOW, NOISE_CLIP_HIGH);
      nextSample = now + NOISE_SAMPLE_PERIOD_US;
    }
    // Yield regularly to the RTOS without waiting on networking.
    vTaskDelay(1);
  }
}

void setup() {
  Serial.begin(115200);
  if (!NOISE_HARDWARE_CONFIRMED) {
    Serial.println("Hardware unconfirmed: set config.local.h before sampling");
    return;
  }
  uint8_t uuid[16];
  esp_fill_random(uuid, sizeof(uuid));
  uuid[6] = (uuid[6] & 0x0f) | 0x40;
  uuid[8] = (uuid[8] & 0x3f) | 0x80;
  snprintf(bootId, sizeof(bootId),
           "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
           uuid[0], uuid[1], uuid[2], uuid[3], uuid[4], uuid[5], uuid[6], uuid[7],
           uuid[8], uuid[9], uuid[10], uuid[11], uuid[12], uuid[13], uuid[14], uuid[15]);
  WiFi.mode(WIFI_STA);
  deviceId = WiFi.macAddress();
  analogReadResolution(12);
  analogSetPinAttenuation(NOISE_ADC_PIN, ADC_11db);
  batches = xQueueCreate(2, sizeof(noise::Batch));
  if (!batches) { Serial.println("Queue allocation failed"); return; }
  // Classic dual-core ESP32: networking cannot block the measurement task.
  if (xTaskCreatePinnedToCore(upload, "upload", 8192, nullptr, 1, nullptr, 0) != pdPASS ||
      xTaskCreatePinnedToCore(sample, "sample", 4096, nullptr, 2, nullptr, 1) != pdPASS) {
    Serial.println("Task allocation failed; restarting");
    ESP.restart();
  }
}

void loop() { delay(1000); }
