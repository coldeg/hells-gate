#pragma once
#include <stdint.h>
#include <stddef.h>

// The captured 33rd bit is required. Never infer it from the 32-bit prefix.
namespace learnedTx {
// I store the observed tail with the 32-bit word; a matching prefix is insufficient.
constexpr size_t capacity = 32;
struct Frame { uint32_t word; uint8_t tail; };
inline bool valid(Frame f) { return (f.word >> 10) != 0 && f.tail <= 1; }
inline void encode(Frame f, uint8_t* out) {
  // At four transport samples per Manchester chip, each source bit occupies one
  // byte (0 -> 0x0F, 1 -> 0xF0). Four zero bytes hold eight physical chips per repeat.
  for (size_t repeat = 0; repeat < 3; ++repeat) {
    for (size_t bit = 0; bit < 32; ++bit)
      out[repeat * 37 + bit] = ((f.word >> (31 - bit)) & 1) ? 0xF0 : 0x0F;
    out[repeat * 37 + 32] = f.tail ? 0xF0 : 0x0F;
    for (size_t hold = 33; hold < 37; ++hold) out[repeat * 37 + hold] = 0;
  }
}
}
