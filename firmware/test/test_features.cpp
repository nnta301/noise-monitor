#include <cassert>
#include <cstring>
#include <iostream>
#include "noise_features.h"

int main() {
  noise::Second second;
  for (int i = 0; i < 20; ++i) {
    second.sample(100, 0, 4095);
    second.sample(100 + i, 0, 4095);
    second.finishWindow();
  }
  auto result = second.finish();
  assert(result.median == 9 && result.peak == 19 && result.samples == 40);
  assert(std::strcmp(result.flag, "ok") == 0);
  noise::Second clipped;
  for (int i = 0; i < 20; ++i) {
    clipped.sample(0, 0, 4095);
    clipped.sample(4095, 0, 4095);
    clipped.finishWindow();
  }
  result = clipped.finish();
  assert(result.clipped == 40 && result.peak == 4095);
  assert(std::strcmp(result.flag, "clipping") == 0);
  noise::Second missing;
  missing.sample(-1, 0, 4095);
  missing.finishWindow();
  result = missing.finish();
  assert(result.invalid == 1 && std::strcmp(result.flag, "missing") == 0);
  noise::Second invalid;
  for (int i = 0; i < 20; ++i) {
    invalid.sample(100, 0, 4095);
    invalid.sample(5000, 0, 4095);
    invalid.finishWindow();
  }
  assert(std::strcmp(invalid.finish().flag, "out_of_range") == 0);
  noise::Second gap;
  for (int i = 0; i < 20; ++i) {
    if (i != 7) gap.sample(123, 0, 4095);
    gap.finishWindow();
  }
  assert(gap.finish().windows == 19);
  assert(std::strcmp(gap.finish().flag, "missing") == 0);
  noise::Second zero;
  for (int i = 0; i < 20; ++i) {
    zero.sample(123, 0, 4095);
    zero.finishWindow();
  }
  assert(zero.finish().median == 0 && zero.finish().peak == 0);
  assert(std::strcmp(zero.finish().flag, "ok") == 0);
  std::cout << "Feature tests passed\n";
}
