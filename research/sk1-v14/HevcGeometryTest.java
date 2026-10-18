package com.limelight.sk1;

import java.io.ByteArrayOutputStream;
import java.nio.ByteBuffer;

public final class HevcGeometryTest {
    private static final class Bits {
        final ByteArrayOutputStream out = new ByteArrayOutputStream();
        int pending, count;
        void u(int width, int value) {
            for (int i = width - 1; i >= 0; i--) {
                pending = (pending << 1) | ((value >>> i) & 1);
                if (++count == 8) { out.write(pending); pending = 0; count = 0; }
            }
        }
        void ue(int value) {
            int x = value + 1, n = 31 - Integer.numberOfLeadingZeros(x);
            u(n, 0); u(n + 1, x);
        }
        byte[] finish() {
            u(1, 1);
            while (count != 0) u(1, 0);
            return out.toByteArray();
        }
    }

    private static byte[] sps(int w, int h, int bottom, int chroma) {
        Bits bits = new Bits();
        bits.u(4, 0); bits.u(3, 0); bits.u(1, 1);
        for (int i = 0; i < 12; i++) bits.u(8, 0);
        bits.ue(0); bits.ue(chroma); bits.ue(w); bits.ue(h);
        bits.u(1, bottom > 0 ? 1 : 0);
        if (bottom > 0) {
            bits.ue(0); bits.ue(0); bits.ue(0); bits.ue(bottom);
        }
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        out.write(0); out.write(0); out.write(0); out.write(1);
        out.write(0x42); out.write(1);
        out.writeBytes(bits.finish());
        return out.toByteArray();
    }

    private static void expect(boolean ok, String message) {
        if (!ok) throw new AssertionError(message);
    }

    public static void main(String[] args) {
        byte[] p = sps(3840, 2176, 8, 1);
        HevcGeometry geo = HevcGeometry.inspect(ByteBuffer.wrap(p), 0, p.length);
        expect(geo != null && geo.width == 3840 && geo.height == 2160
                && geo.bottom == 16, "4K padded HEVC");
        byte[] q = sps(1920, 1080, 0, 1);
        geo = HevcGeometry.inspect(ByteBuffer.wrap(q), 0, q.length);
        expect(geo != null && geo.width == 1920 && geo.height == 1080, "1080p");
        expect(HevcGeometry.inspect(ByteBuffer.wrap(p), p.length-3, 3) == null, "short buffer");
        System.out.println("PASS HEVC geometry: 3840x2176 -> 3840x2160, 1080p, bounds");
    }
}
