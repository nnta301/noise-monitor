#include <cassert>
#include <iostream>
#include "noise_telemetry.h"

int main() {
  const char* device = "synthetic-firmware-contract-test";
  const char* boot = "123e4567-e89b-42d3-a456-426614174000";
  noise::Batch batch;
  // Exercise values beyond 32-bit millis/sequence, including all quality flags.
  batch.measuredMs = 5000000000ULL;
  batch.sequence = 5000000000ULL;
  for (unsigned i = 0; i < noise::kBatchSeconds; ++i) {
    noise::Second second;
    for (unsigned window = 0; window < noise::kWindows; ++window) {
      if (i != 3) {
        second.sample(i == 1 ? 0 : 100, 0, 4095);
        second.sample(200, 0, 4095);
        if (i == 2) second.sample(-1, 0, 4095);
      }
      second.finishWindow();
    }
    batch.features[i] = second.finish();
  }
  StaticJsonDocument<2048> json;
  for (unsigned i = 0; i < 2; ++i) {
    noise::fillTelemetry(json, batch, device, boot, "Asia/Ho_Chi_Minh");
    assert(!json.overflowed());
    assert(json["measured_at"].as<uint64_t>() == batch.measuredMs);
    assert(json["sequence"].as<uint64_t>() == batch.sequence);
    assert(json["median_p2p"][3].isNull());
    serializeJson(json, std::cout);
    std::cout << '\n';
    batch.measuredMs += 10000;
    ++batch.sequence;
  }
  StaticJsonDocument<512> response;
  response["outcome"] = "accepted";
  response["packet_key"]["device_id"] = device;
  response["packet_key"]["boot_id"] = boot;
  response["packet_key"]["sequence"] = batch.sequence;
  auto valid = [&]() {
    return noise::matchesAcknowledgement(response.as<JsonVariantConst>(), batch, device, boot);
  };
  assert(valid());
  response["outcome"] = "duplicate";
  assert(valid());
  response["packet_key"]["sequence"] = batch.sequence - 1;
  assert(!valid());
  response["packet_key"]["sequence"] = "5000000002";
  assert(!valid());
  response["packet_key"]["sequence"] = batch.sequence;
  response["packet_key"]["boot_id"] = "wrong-boot";
  assert(!valid());
  response["packet_key"]["boot_id"] = boot;
  response["outcome"] = "unknown";
  assert(!valid());
  response["outcome"] = "accepted";
  response["unexpected"] = true;
  assert(!valid());
}
