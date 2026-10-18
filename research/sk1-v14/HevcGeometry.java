package com.limelight.sk1;

import java.nio.ByteBuffer;
import java.util.Arrays;

/**
 * Independent reconstruction of HEVC SPS geometry handling found in the v14 APK.
 * Not the original developer's source code. Used for documentation and tests.
 */
public final class HevcGeometry {
    public final int codedWidth, codedHeight, left, top, right, bottom, width, height;

    private HevcGeometry(int w, int h, int l, int t, int r, int b) {
        codedWidth = w; codedHeight = h;
        left = l; top = t; right = r; bottom = b;
        width = w - l - r; height = h - t - b;
    }

    /** Scans an Annex-B HEVC buffer for an SPS (NAL unit type 33). */
    public static HevcGeometry inspect(ByteBuffer data, int offset, int size) {
        if (data == null || offset < 0 || size < 0 || offset > data.limit() - size) return null;
        final int end = offset + size;
        try {
            for (int p = offset; p + 5 <= end; p++) {
                final int prefix = startCode(data, p, end);
                if (prefix == 0) continue;
                final int nal = p + prefix;
                if (nal + 2 > end) return null;
                final int type = (data.get(nal) & 0x7e) >>> 1;
                if (type != 33) { p = nal; continue; }
                if ((data.get(nal + 1) & 7) == 0) return null;

                final int start = nal + 2;
                int finish = start;
                while (finish < end && startCode(data, finish, end) == 0) finish++;
                byte[] rbsp = new byte[finish - start];
                int used = 0, zeros = 0;
                for (int i = start; i < finish; i++) {
                    int value = data.get(i) & 0xff;
                    if (zeros >= 2 && value == 3) { zeros = 0; continue; }
                    rbsp[used++] = (byte) value;
                    zeros = value == 0 ? zeros + 1 : 0;
                }
                return parse(Arrays.copyOf(rbsp, used));
            }
        } catch (IllegalArgumentException | IndexOutOfBoundsException e) {
            return null;
        }
        return null;
    }

    private static int startCode(ByteBuffer data, int i, int end) {
        if (i + 3 > end || data.get(i) != 0 || data.get(i + 1) != 0) return 0;
        if (data.get(i + 2) == 1) return 3;
        return i + 4 <= end && data.get(i + 2) == 0 && data.get(i + 3) == 1 ? 4 : 0;
    }

    private static HevcGeometry parse(byte[] rbsp) {
        Bits bits = new Bits(rbsp);
        bits.skip(4);
        final int subLayers = bits.u(3);
        if (subLayers > 6) return null;
        bits.skip(97); // temporal nesting flag and general profile_tier_level
        boolean[] profile = new boolean[subLayers];
        boolean[] level = new boolean[subLayers];
        for (int i = 0; i < subLayers; i++) {
            profile[i] = bits.u(1) != 0;
            level[i] = bits.u(1) != 0;
        }
        if (subLayers > 0) bits.skip((8 - subLayers) * 2);
        for (int i = 0; i < subLayers; i++) {
            if (profile[i]) bits.skip(88);
            if (level[i]) bits.skip(8);
        }

        bits.ue(); // sps_seq_parameter_set_id
        int chroma = bits.ue();
        if (chroma > 3) return null;
        boolean separate = chroma == 3 && bits.u(1) != 0;
        int codedW = bits.ue(), codedH = bits.ue();
        if (codedW <= 0 || codedH <= 0 || codedW > 32768 || codedH > 32768) return null;

        int l = 0, r = 0, t = 0, b = 0;
        if (bits.u(1) != 0) {
            l = bits.ue(); r = bits.ue(); t = bits.ue(); b = bits.ue();
        }
        int chromaW = (!separate && (chroma == 1 || chroma == 2)) ? 2 : 1;
        int chromaH = (!separate && chroma == 1) ? 2 : 1;
        if ((long) (l + r) * chromaW >= codedW || (long) (t + b) * chromaH >= codedH) {
            return null;
        }
        return new HevcGeometry(codedW, codedH,
                l * chromaW, t * chromaH, r * chromaW, b * chromaH);
    }

    @Override public String toString() {
        return "coded=" + codedWidth + "x" + codedHeight
                + " visible=" + width + "x" + height
                + " cropLTRB=" + left + "," + top + "," + right + "," + bottom;
    }

    private static final class Bits {
        final byte[] data;
        int position;
        Bits(byte[] data) { this.data = data; }

        void skip(int n) {
            if (n < 0 || position > data.length * 8 - n)
                throw new IllegalArgumentException("Short SPS");
            position += n;
        }
        int u(int n) {
            if (n < 0 || n > 31 || position > data.length * 8 - n)
                throw new IllegalArgumentException("Short SPS");
            int value = 0;
            for (int i = 0; i < n; i++) {
                value = value << 1
                        | ((data[position >>> 3] >>> (7 - (position & 7))) & 1);
                position++;
            }
            return value;
        }
        int ue() {
            int zeros = 0;
            while (u(1) == 0) {
                if (++zeros > 30) throw new IllegalArgumentException("Invalid Exp-Golomb");
            }
            return ((1 << zeros) - 1) + u(zeros);
        }
    }
}
