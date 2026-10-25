/*
 * SPDX-License-Identifier: GPL-3.0-only
 * Optimized BT.709 I420 -> RGBA8888 for the SDR PyroWave CPU staging path.
 * Independent of Android/Vulkan to permit host-side correctness testing.
 */
#pragma once

#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>

namespace sk1_pyrowave {

// 16 fractional bits leave ample headroom for any 8-bit BT.709 sample.
constexpr int kFractionBits = 16;
constexpr std::int32_t kRounding = 1 << (kFractionBits - 1);

struct Bt709Lut {
  std::array<std::int32_t, 256> y {};
  std::array<std::int32_t, 256> red_from_v {};
  std::array<std::int32_t, 256> green_from_u {};
  std::array<std::int32_t, 256> green_from_v {};
  std::array<std::int32_t, 256> blue_from_u {};

  explicit Bt709Lut(bool full_range) noexcept {
    const double luma_scale = full_range ? 1.0 : 255.0 / 219.0;
    const double chroma_scale = full_range ? 1.0 : 255.0 / 224.0;
    constexpr double unit = static_cast<double>(1 << kFractionBits);
    for (int sample = 0; sample < 256; ++sample) {
      const double luma = (sample - (full_range ? 0 : 16)) * luma_scale;
      const double chroma = (sample - 128) * chroma_scale;
      y[sample] = static_cast<std::int32_t>(std::lround(luma * unit));
      red_from_v[sample] = static_cast<std::int32_t>(std::lround(chroma * 1.5748 * unit));
      green_from_u[sample] = static_cast<std::int32_t>(std::lround(chroma * -0.1873 * unit));
      green_from_v[sample] = static_cast<std::int32_t>(std::lround(chroma * -0.4681 * unit));
      blue_from_u[sample] = static_cast<std::int32_t>(std::lround(chroma * 1.8556 * unit));
    }
  }
};

inline std::uint8_t clamp_fixed(std::int32_t fixed) noexcept {
  // The clipped interval is nonnegative, so integer rounding here matches
  // round-to-nearest for all values that are visible after clipping.
  if (fixed <= 0) return 0;
  constexpr std::int32_t max_fixed = 255 << kFractionBits;
  if (fixed >= max_fixed) return 255;
  return static_cast<std::uint8_t>((fixed + kRounding) >> kFractionBits);
}

inline void write_rgba(std::uint8_t *dst, std::uint8_t luma_sample,
                       std::int32_t r, std::int32_t g, std::int32_t b,
                       const Bt709Lut &lut) noexcept {
  const auto luma = lut.y[luma_sample];
  dst[0] = clamp_fixed(luma + r);
  dst[1] = clamp_fixed(luma + g);
  dst[2] = clamp_fixed(luma + b);
  dst[3] = 255;
}

// Input is a tightly packed, even-sized YUV420P image (width/height are even).
// Output may be cropped by the consumer Surface and may have stride padding.
inline void i420_to_rgba(const std::uint8_t *y, const std::uint8_t *u,
                         const std::uint8_t *v, int width,
                         std::uint8_t *dst, std::size_t dst_stride_bytes,
                         int copy_width, int copy_height,
                         const Bt709Lut &lut) noexcept {
  const int uv_stride = width / 2;
  for (int row = 0; row < copy_height; row += 2) {
    const auto *y0 = y + static_cast<std::size_t>(row) * width;
    const auto *y1 = y0 + width;
    auto *dst0 = dst + static_cast<std::size_t>(row) * dst_stride_bytes;
    auto *dst1 = dst0 + dst_stride_bytes;
    const auto uv_row = static_cast<std::size_t>(row / 2) * uv_stride;
    for (int col = 0; col < copy_width; col += 2) {
      const auto uv_index = uv_row + col / 2;
      const auto cb = u[uv_index];
      const auto cr = v[uv_index];
      const auto r = lut.red_from_v[cr];
      const auto g = lut.green_from_u[cb] + lut.green_from_v[cr];
      const auto b = lut.blue_from_u[cb];
      write_rgba(dst0 + static_cast<std::size_t>(col) * 4, y0[col], r, g, b, lut);
      if (col + 1 < copy_width) {
        write_rgba(dst0 + static_cast<std::size_t>(col + 1) * 4, y0[col + 1], r, g, b, lut);
      }
      if (row + 1 < copy_height) {
        write_rgba(dst1 + static_cast<std::size_t>(col) * 4, y1[col], r, g, b, lut);
        if (col + 1 < copy_width) {
          write_rgba(dst1 + static_cast<std::size_t>(col + 1) * 4, y1[col + 1], r, g, b, lut);
        }
      }
    }
  }
}

}  // namespace sk1_pyrowave
