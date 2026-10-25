/*
 * SPDX-License-Identifier: GPL-3.0-only
 * SK1 experimental ARMv7 NEON conversion from tightly packed I420 to RGBA.
 *
 * This translation unit is built as .cpp.neon by Android NDK ndk-build on
 * armeabi-v7a. It is called only after a runtime NEON feature check.
 * Coefficients use Q13, matching the existing BT.709 staging conversion
 * within one output code value for every 8-bit Y/Cb/Cr combination.
 */
#include "pyrowave_sdr_fast_convert.hpp"

#include <arm_neon.h>

namespace sk1_pyrowave {
namespace {

constexpr int kShift = 13;
constexpr int kHalf = 1 << (kShift - 1);

struct Coefficients {
  int16_t y;
  int16_t red_v;
  int16_t green_u;
  int16_t green_v;
  int16_t blue_u;
  int16_t y_offset;
};

constexpr Coefficients kBt709Limited {9539, 14686, -1747, -4365, 17305, 16};
constexpr Coefficients kBt709Full {8192, 12901, -1534, -3835, 15201, 0};

inline uint8x8_t rounded_and_clamped(int32x4_t low, int32x4_t high) noexcept {
  const auto offset = vdupq_n_s32(kHalf);
  const auto lo = vqshrun_n_s32(vaddq_s32(low, offset), kShift);
  const auto hi = vqshrun_n_s32(vaddq_s32(high, offset), kShift);
  return vqmovn_u16(vcombine_u16(lo, hi));
}

// Eight output pixels. Cb/Cr have already been horizontally duplicated.
inline void convert_eight(const uint8_t *src_y, uint8_t *dst,
                          int16x8_t cb, int16x8_t cr,
                          const Coefficients &c) noexcept {
  const auto yy = vreinterpretq_s16_u16(vmovl_u8(vld1_u8(src_y)));
  const auto y = vsubq_s16(yy, vdupq_n_s16(c.y_offset));
  const auto cb_lo = vget_low_s16(cb);
  const auto cb_hi = vget_high_s16(cb);
  const auto cr_lo = vget_low_s16(cr);
  const auto cr_hi = vget_high_s16(cr);
  const auto yl = vmull_n_s16(vget_low_s16(y), c.y);
  const auto yh = vmull_n_s16(vget_high_s16(y), c.y);

  const auto red = rounded_and_clamped(
      vmlal_n_s16(yl, cr_lo, c.red_v),
      vmlal_n_s16(yh, cr_hi, c.red_v));
  const auto green = rounded_and_clamped(
      vmlal_n_s16(vmlal_n_s16(yl, cb_lo, c.green_u), cr_lo, c.green_v),
      vmlal_n_s16(vmlal_n_s16(yh, cb_hi, c.green_u), cr_hi, c.green_v));
  const auto blue = rounded_and_clamped(
      vmlal_n_s16(yl, cb_lo, c.blue_u),
      vmlal_n_s16(yh, cb_hi, c.blue_u));

  uint8x8x4_t rgba {};
  rgba.val[0] = red;
  rgba.val[1] = green;
  rgba.val[2] = blue;
  rgba.val[3] = vdup_n_u8(255);
  vst4_u8(dst, rgba);
}

inline uint8_t q13_to_byte(int32_t value) noexcept {
  if (value <= 0) return 0;
  if (value >= 255 * (1 << kShift)) return 255;
  return static_cast<uint8_t>((value + kHalf) >> kShift);
}

inline void scalar_pixel(uint8_t *dst, uint8_t sample, int32_t r,
                         int32_t g, int32_t b, const Coefficients &c) noexcept {
  const int32_t luma = (static_cast<int32_t>(sample) - c.y_offset) * c.y;
  dst[0] = q13_to_byte(luma + r);
  dst[1] = q13_to_byte(luma + g);
  dst[2] = q13_to_byte(luma + b);
  dst[3] = 255;
}

}  // namespace

void i420_to_rgba_neon(const uint8_t *y, const uint8_t *u,
                       const uint8_t *v, int width,
                       uint8_t *dst, size_t dst_stride,
                       int copy_width, int copy_height,
                       bool full_range) noexcept {
  const Coefficients &c = full_range ? kBt709Full : kBt709Limited;
  const int chroma_stride = width / 2;

  for (int row = 0; row < copy_height; row += 2) {
    const auto *y0 = y + static_cast<size_t>(row) * width;
    const auto *y1 = y0 + width;
    auto *d0 = dst + static_cast<size_t>(row) * dst_stride;
    auto *d1 = d0 + dst_stride;
    const auto chroma_offset = static_cast<size_t>(row / 2) * chroma_stride;
    int col = 0;

    // Eight Cb/Cr samples feed 16 horizontally duplicated luma pixels.
    // Process the next row with the same Cb/Cr values (4:2:0 sampling).
    for (; col + 16 <= copy_width; col += 16) {
      const auto u8 = vld1_u8(u + chroma_offset + col / 2);
      const auto v8 = vld1_u8(v + chroma_offset + col / 2);
      const auto u_dupe = vzip_u8(u8, u8);
      const auto v_dupe = vzip_u8(v8, v8);

      const auto cb0 = vsubq_s16(
          vreinterpretq_s16_u16(vmovl_u8(u_dupe.val[0])),
          vdupq_n_s16(128));
      const auto cr0 = vsubq_s16(
          vreinterpretq_s16_u16(vmovl_u8(v_dupe.val[0])),
          vdupq_n_s16(128));
      const auto cb1 = vsubq_s16(
          vreinterpretq_s16_u16(vmovl_u8(u_dupe.val[1])),
          vdupq_n_s16(128));
      const auto cr1 = vsubq_s16(
          vreinterpretq_s16_u16(vmovl_u8(v_dupe.val[1])),
          vdupq_n_s16(128));

      convert_eight(y0 + col, d0 + static_cast<size_t>(col) * 4u, cb0, cr0, c);
      convert_eight(y0 + col + 8, d0 + static_cast<size_t>(col + 8) * 4u, cb1, cr1, c);
      if (row + 1 < copy_height) {
        convert_eight(y1 + col, d1 + static_cast<size_t>(col) * 4u, cb0, cr0, c);
        convert_eight(y1 + col + 8, d1 + static_cast<size_t>(col + 8) * 4u, cb1, cr1, c);
      }
    }

    // Right/bottom partial tiles: never read beyond source or Surface crop.
    for (; col < copy_width; col += 2) {
      const auto index = chroma_offset + col / 2;
      const int32_t cb = static_cast<int32_t>(u[index]) - 128;
      const int32_t cr = static_cast<int32_t>(v[index]) - 128;
      const int32_t r = cr * c.red_v;
      const int32_t g = cb * c.green_u + cr * c.green_v;
      const int32_t b = cb * c.blue_u;
      scalar_pixel(d0 + static_cast<size_t>(col) * 4u, y0[col], r, g, b, c);
      if (col + 1 < copy_width) {
        scalar_pixel(d0 + static_cast<size_t>(col + 1) * 4u, y0[col + 1], r, g, b, c);
      }
      if (row + 1 < copy_height) {
        scalar_pixel(d1 + static_cast<size_t>(col) * 4u, y1[col], r, g, b, c);
        if (col + 1 < copy_width) {
          scalar_pixel(d1 + static_cast<size_t>(col + 1) * 4u, y1[col + 1], r, g, b, c);
        }
      }
    }
  }
}

}  // namespace sk1_pyrowave
