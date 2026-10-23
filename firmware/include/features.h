#pragma once

#include <algorithm>
#include <array>
#include <cstdint>

namespace noise {
constexpr unsigned kWindows = 20;
constexpr unsigned kBatchSeconds = 10;
constexpr uint64_t kWindowUs = 50000;

struct Feature {
  int median = 0;
  int peak = 0;
  uint32_t samples = 0;
  uint32_t invalid = 0;
  uint32_t clipped = 0;
  unsigned windows = 0;
  const char* flag = "missing";
};

// Holds only window extrema and numeric features, never a waveform.
class Second {
 public:
  void sample(int value, int clipLow, int clipHigh) {
    if (value < 0 || value > 4095) { ++invalid_; return; }
    ++count_;
    if (value <= clipLow || value >= clipHigh) ++clipped_;
    low_ = std::min(low_, value);
    high_ = std::max(high_, value);
    ++windowCount_;
  }

  void finishWindow() {
    if (windowCount_ && windows_ < kWindows) values_[windows_++] = high_ - low_;
    else ++missingWindows_;
    low_ = 4095;
    high_ = 0;
    windowCount_ = 0;
  }

  Feature finish() const {
    Feature result;
    result.samples = count_;
    result.invalid = invalid_;
    result.clipped = clipped_;
    result.windows = windows_;
    // An incomplete second must not look like a full valid measurement.
    if (windows_ != kWindows || missingWindows_) return result;
    auto sorted = values_;
    std::sort(sorted.begin(), sorted.begin() + windows_);
    result.median = (sorted[9] + sorted[10]) / 2;
    result.peak = sorted[19];
    result.flag = invalid_ ? "out_of_range" : clipped_ ? "clipping" : "ok";
    return result;
  }

 private:
  std::array<int, kWindows> values_{};
  unsigned windows_ = 0, missingWindows_ = 0;
  uint32_t count_ = 0, invalid_ = 0, clipped_ = 0, windowCount_ = 0;
  int low_ = 4095, high_ = 0;
};

struct Batch {
  uint64_t measuredMs = 0;
  uint64_t sequence = 0;
  std::array<Feature, kBatchSeconds> features{};
};
}  // namespace noise
