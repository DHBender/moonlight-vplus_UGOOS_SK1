package com.limelight.sk1;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.graphics.Rect;
import android.media.MediaCodec;
import android.media.MediaCrypto;
import android.media.MediaFormat;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.Surface;
import android.view.SurfaceControl;
import android.view.SurfaceView;
import android.view.View;

import com.limelight.R;

import java.io.IOException;
import java.lang.ref.WeakReference;
import java.nio.ByteBuffer;

/**
 * Isolated reconstruction of the owner-tested SK1 v14 DEFAULT HEVC path.
 *
 * Verified against v14 APK (sha256 aea9fb5a6661c90b6dccee462498026eb8310b51e55d9558ae7656020226eedf):
 * direct SurfaceView is default; HEVC uses KEY_LOW_LATENCY=1 without the vendor
 * low-latency flags; sync and timed output releases are immediate; input frames
 * can have trailing zero padding stripped; v14 applies 3840x2176/3840x2160 crop.
 *
 * This is a source reconstruction, NOT byte-identical to the v14 dex.
 * The optional v14 outputMode=0 diagnostic OpenGL surface is not reconstructed.
 */
public final class TextureBridge {
    private static final String TAG = "SK1Texture";
    private static final Handler UI = new Handler(Looper.getMainLooper());
    private static final String[] V14_VENDOR_KEYS = {
        "vdec-lowlatency",
        "vendor.low-latency.enable",
        "vendor.amlogic.lowlatency.mode",
        "vendor.amlogic.tunnel.mode",
        "vendor.amlogic.frame-skip.enable"
    };

    private static volatile WeakReference<Activity> activityRef = new WeakReference<>(null);
    private static volatile MediaCodec hevcCodec;
    private static volatile boolean directOutput;
    private static volatile HevcGeometry sourceGeometry;
    private static volatile int outputWidth;
    private static volatile int outputHeight;
    private static SurfaceView cropView;
    private static View.OnLayoutChangeListener cropListener;
    private static long trimmedFrames;
    private static long trimmedBytes;
    private static volatile int sessionGeneration;

    private TextureBridge() {}

    public static void attach(Activity activity) {
        activityRef = new WeakReference<>(activity);
        Log.i(TAG, "SK1 v14 direct HEVC bridge attached");
    }

    public static void configure(MediaCodec codec, MediaFormat format, Surface surface,
                                 MediaCrypto crypto, int flags) throws IOException {
        if (!"video/hevc".equals(format.getString(MediaFormat.KEY_MIME))) {
            codec.configure(format, surface, crypto, flags);
            return;
        }
        if (surface == null || !surface.isValid()) {
            throw new IllegalArgumentException("SK1 HEVC output Surface is not valid");
        }

        // The tested v14 APK selects output-mode=1 (direct SurfaceView) by default.
        // Only the direct path is reconstructed; leave optional GL/framegen paths to
        // upstream if they select a different surface.
        synchronized (TextureBridge.class) {
            hevcCodec = codec;
            directOutput = true;
            sourceGeometry = null;
            outputWidth = 0;
            outputHeight = 0;
            trimmedFrames = 0L;
            trimmedBytes = 0L;
            ++sessionGeneration;
        }
        for (String key : V14_VENDOR_KEYS) {
            format.removeKey(key);
        }
        format.setInteger(MediaFormat.KEY_LOW_LATENCY, 1);
        for (String csdName : new String[] {"csd-0", "csd-1"}) {
            if (format.containsKey(csdName)) {
                ByteBuffer csd = format.getByteBuffer(csdName);
                if (csd != null) inspectSourceGeometry(csd, csd.position(), csd.remaining());
            }
        }
        Log.i(TAG, "SK1 v14 HEVC direct SurfaceView, low-latency=1, vendor flags cleared: " + format);
        try {
            codec.configure(format, surface, crypto, flags);
        } catch (IOException | RuntimeException e) {
            synchronized (TextureBridge.class) {
                if (hevcCodec == codec) {
                    hevcCodec = null;
                    directOutput = false;
                    ++sessionGeneration;
                }
            }
            throw e;
        }
    }

    public static void beginSubmit() {
        // Diagnostic hook maintained for compatibility with the original bridge.
    }

    public static int dequeueInput(MediaCodec codec, long timeoutUs) {
        return codec.dequeueInputBuffer(timeoutUs);
    }

    public static void queueInput(MediaCodec codec, int index, int offset, int size,
                                  long presentationTimeUs, int flags) {
        int inputSize = size;
        if (codec == hevcCodec && directOutput && size > 0) {
            if ((flags & MediaCodec.BUFFER_FLAG_CODEC_CONFIG) != 0) {
                ByteBuffer input = codec.getInputBuffer(index);
                if (input != null) inspectSourceGeometry(input, offset, size);
            }
            // v14 trims Annex-B trailing zero padding for normal video frames.
            if ((flags & (MediaCodec.BUFFER_FLAG_CODEC_CONFIG | MediaCodec.BUFFER_FLAG_END_OF_STREAM)) == 0) {
                ByteBuffer input = codec.getInputBuffer(index);
                if (input != null && offset >= 0 && size <= input.limit() - offset) {
                    while (inputSize > 0 && input.get(offset + inputSize - 1) == 0) {
                        --inputSize;
                    }
                    if (inputSize > 0 && inputSize < size) {
                        long count;
                        synchronized (TextureBridge.class) {
                            count = ++trimmedFrames;
                            trimmedBytes += size - inputSize;
                        }
                        if (count <= 3 || count % 300 == 0) {
                            Log.i(TAG, "HEVC zero-tail trimmed: frames=" + count +
                                    " removedThisFrame=" + (size - inputSize) +
                                    " totalBytes=" + trimmedBytes);
                        }
                    } else {
                        inputSize = size;
                    }
                }
            }
        }
        codec.queueInputBuffer(index, offset, inputSize, presentationTimeUs, flags);
    }

    public static int dequeueOutput(MediaCodec codec, MediaCodec.BufferInfo info, long timeoutUs) {
        int index = codec.dequeueOutputBuffer(info, timeoutUs);
        if (index == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
            noteOutputFormat(codec, codec.getOutputFormat());
        }
        return index;
    }

    public static void noteOutput(MediaCodec codec, int index, MediaCodec.BufferInfo info) {
        // Keep the API shape used by original v14; telemetry is not required
        // for rendering, but the decoder callback still calls this hook.
    }

    public static void releaseBoolean(MediaCodec codec, int index, boolean render) {
        codec.releaseOutputBuffer(index, render);
    }

    public static void releaseTimed(MediaCodec codec, int index, long presentationTimeNs) {
        if (codec == hevcCodec && directOutput) {
            // THE critical v14 behavior: don't schedule these frames on timestamps.
            codec.releaseOutputBuffer(index, true);
        } else {
            codec.releaseOutputBuffer(index, presentationTimeNs);
        }
    }

    public static void releaseCodec(MediaCodec codec) {
        boolean tracked = codec == hevcCodec;
        try {
            codec.release();
        } finally {
            if (tracked) {
                synchronized (TextureBridge.class) {
                    if (codec == hevcCodec) {
                        hevcCodec = null;
                        directOutput = false;
                        sourceGeometry = null;
                        outputWidth = 0;
                        outputHeight = 0;
                        ++sessionGeneration;
                    }
                }
                UI.post(TextureBridge::resetCropSurface);
            }
        }
    }

    private static void inspectSourceGeometry(ByteBuffer input, int offset, int size) {
        HevcGeometry g = HevcGeometry.inspect(input, offset, size);
        if (g != null) {
            sourceGeometry = g;
            Log.i(TAG, "v14 SPS geometry " + g);
            requestCropSurface();
        }
    }

    public static void noteOutputFormat(MediaCodec codec, MediaFormat format) {
        if (codec != hevcCodec || !directOutput) return;
        try {
            int width = format.getInteger(MediaFormat.KEY_WIDTH);
            int height = format.getInteger(MediaFormat.KEY_HEIGHT);
            if (format.containsKey("crop-left") && format.containsKey("crop-right")) {
                width = format.getInteger("crop-right") - format.getInteger("crop-left") + 1;
            }
            if (format.containsKey("crop-top") && format.containsKey("crop-bottom")) {
                height = format.getInteger("crop-bottom") - format.getInteger("crop-top") + 1;
            }
            outputWidth = width;
            outputHeight = height;
            Log.i(TAG, "v14 output geometry " + width + "x" + height);
            requestCropSurface();
        } catch (RuntimeException e) {
            Log.w(TAG, "Cannot inspect v14 output format", e);
        }
    }

    private static void requestCropSurface() {
        if (Build.VERSION.SDK_INT < 33 || outputWidth == 0 || outputHeight == 0) return;
        final MediaCodec codec = hevcCodec;
        final int generation = sessionGeneration;
        UI.post(() -> {
            Activity activity = activityRef.get();
            if (codec == null || codec != hevcCodec || !directOutput ||
                    generation != sessionGeneration || activity == null || activity.isFinishing()) return;
            SurfaceView view = activity.findViewById(R.id.surfaceView);
            if (view == null) return;
            if (cropView != view) {
                resetCropSurface();
                cropView = view;
                cropListener = (v, left, top, right, bottom, oldLeft, oldTop, oldRight, oldBottom) ->
                        requestCropSurface();
                view.addOnLayoutChangeListener(cropListener);
            }
            applyCropSurface(view);
        });
    }

    @SuppressLint("NewApi")
    private static void applyCropSurface(SurfaceView view) {
        if (Build.VERSION.SDK_INT < 33) return;
        int w = view.getWidth(), h = view.getHeight();
        if (w <= 0 || h <= 0) return;
        HevcGeometry g = sourceGeometry;
        boolean needsCrop = g != null &&
                g.codedWidth == 3840 && g.codedHeight == 2176 &&
                g.width == 3840 && g.height == 2160 &&
                g.left == 0 && g.right == 0 && g.top == 0 && g.bottom == 16 &&
                outputWidth == g.width && outputHeight == g.height &&
                ((long) h * g.bottom) % g.height == 0;
        int bottom = needsCrop ? (int) (((long) h * g.bottom) / g.height) : 0;
        if (bottom >= h) return;
        Rect crop = needsCrop ? new Rect(0, 0, w, h - bottom) : null;
        float scaleY = needsCrop ? (float) h / (h - bottom) : 1f;
        try {
            SurfaceControl control = view.getSurfaceControl();
            if (control != null && control.isValid()) {
                try (SurfaceControl.Transaction txn = new SurfaceControl.Transaction()) {
                    txn.setCrop(control, crop).setScale(control, 1f, scaleY).apply();
                }
                Log.i(TAG, "v14 crop-test applied=" + needsCrop + " view=" + w +
                        "x" + h + " crop=" + crop + " scaleY=" + scaleY);
            }
        } catch (RuntimeException e) {
            Log.w(TAG, "v14 crop transaction rejected", e);
        }
    }

    @SuppressLint("NewApi")
    private static void resetCropSurface() {
        SurfaceView previous = cropView;
        if (previous != null && cropListener != null) {
            previous.removeOnLayoutChangeListener(cropListener);
        }
        cropView = null;
        cropListener = null;
        if (previous == null || Build.VERSION.SDK_INT < 33) return;
        try {
            SurfaceControl control = previous.getSurfaceControl();
            if (control != null && control.isValid()) {
                try (SurfaceControl.Transaction txn = new SurfaceControl.Transaction()) {
                    txn.setCrop(control, null).setScale(control, 1f, 1f).apply();
                }
            }
        } catch (RuntimeException e) {
            Log.w(TAG, "v14 crop reset", e);
        }
    }
}
