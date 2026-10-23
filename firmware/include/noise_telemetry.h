#pragma once

#include <ArduinoJson.h>
#include <cstring>
#include "noise_features.h"

namespace noise {
// Shared by the device and host contract tests: never serialize raw samples.
inline void fillTelemetry(JsonDocument& json, const Batch& batch,
                          const char* deviceId, const char* bootId,
                          const char* timezone) {
  json.clear();
  json["schema_version"] = "v1";
  json["device_id"] = deviceId;
  json["boot_id"] = bootId;
  json["sequence"] = batch.sequence;
  json["measured_at"] = batch.measuredMs;
  json["timezone"] = timezone;
  json["time_sync_status"] = "monotonic";
  auto medians = json.createNestedArray("median_p2p");
  auto peaks = json.createNestedArray("peak_p2p");
  auto flags = json.createNestedArray("quality_flags");
  for (const auto& feature : batch.features) {
    if (std::strcmp(feature.flag, "missing") == 0) {
      medians.add(nullptr);
      peaks.add(nullptr);
    } else {
      medians.add(feature.median);
      peaks.add(feature.peak);
    }
    flags.add(feature.flag);
  }
}

inline bool matchesAcknowledgement(JsonVariantConst json, const Batch& batch,
                                   const char* deviceId, const char* bootId) {
  const auto key = json["packet_key"];
  const char* outcome = json["outcome"] | "";
  return json.is<JsonObjectConst>() && json.size() == 2 &&
         (std::strcmp(outcome, "accepted") == 0 ||
          std::strcmp(outcome, "duplicate") == 0) &&
         key.is<JsonObjectConst>() && key.size() == 3 &&
         key["sequence"].is<uint64_t>() &&
         key["sequence"].as<uint64_t>() == batch.sequence &&
         std::strcmp(key["device_id"] | "", deviceId) == 0 &&
         std::strcmp(key["boot_id"] | "", bootId) == 0;
}
}  // namespace noise
