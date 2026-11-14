#!/usr/bin/env python3
"""Merge checked HEVC v14 bridge into pinned V+ 12.15.7.

Rebuild the two integration files from exact upstream sources, then reattach
the known-good v14 MediaCodec interception points. Fail on unexpected changes
to avoid silently losing the user's low-latency SK1 HEVC path.
"""
from __future__ import annotations
import os
import re
import subprocess
from pathlib import Path

REF = os.environ.get("UPSTREAM_REF", "refs/remotes/sk1-upstream/v12.15.7")

def upstream(p: str) -> str:
    return subprocess.check_output(["git", "show", f"{REF}:{p}"]).decode("utf-8")

def rep(s: str, old: str, new: str, n: int = 1) -> str:
    found = s.count(old)
    if found != n:
        raise RuntimeError(f"Expected {n} matches, found {found}: {old[:120]!r}")
    return s.replace(old, new)

def write(p: str, s: str) -> None:
    path = Path(p)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(s, encoding="utf-8", newline="\n")
    print(f"SK1 generated {p}: {len(s)} characters", flush=True)

def renderer():
    p = "app/src/main/java/com/limelight/binding/video/MediaCodecDecoderRenderer.kt"
    s = upstream(p)
    s = rep(s, "import com.limelight.preferences.PreferenceConfiguration\n",
            "import com.limelight.preferences.PreferenceConfiguration\nimport com.limelight.sk1.TextureBridge\n")
    s = rep(s, ") : VideoDecoderRenderer() {\n",
            ") : VideoDecoderRenderer() {\n\n"
            "    // SK1 v14 low-latency HEVC, retaining new upstream codec/resize logic.\n"
            "    init { TextureBridge.attach(activity) }\n")
    s = rep(s, "videoDecoder!!.configure(format, outSurface, null, 0)",
            "TextureBridge.configure(videoDecoder!!, format, outSurface, null, 0)")
    s = rep(s, "videoDecoder!!.release()", "TextureBridge.releaseCodec(videoDecoder!!)", 3)
    s = rep(s, "videoDecoder!!.releaseOutputBuffer(bufferIndex, hostCadenceClock.presentTimeNs(hostPtsUs, frameIntervalNs))",
            "TextureBridge.releaseTimed(videoDecoder!!, bufferIndex, hostCadenceClock.presentTimeNs(hostPtsUs, frameIntervalNs))")
    s = rep(s, "videoDecoder!!.releaseOutputBuffer(bufferIndex, 0)",
            "TextureBridge.releaseTimed(videoDecoder!!, bufferIndex, 0)")
    s = rep(s, "videoDecoder!!.releaseOutputBuffer(bufferIndex, System.nanoTime())",
            "TextureBridge.releaseTimed(videoDecoder!!, bufferIndex, System.nanoTime())")
    s = rep(s, "                numFramesOut++\n"
            "                hdr10PlusOutputObserver.observeOutput(codec, index, info.presentationTimeUs)",
            "                TextureBridge.noteOutput(codec, index, info)\n"
            "                numFramesOut++\n"
            "                hdr10PlusOutputObserver.observeOutput(codec, index, info.presentationTimeUs)")
    s = rep(s, '                handleOutputFormatChanged(format, "async")',
            '                handleOutputFormatChanged(format, "async")\n'
            '                TextureBridge.noteOutputFormat(codec, format)')
    s = rep(s, "videoDecoder!!.dequeueOutputBuffer(info, 50000)",
            "TextureBridge.dequeueOutput(videoDecoder!!, info, 50000)")
    s = rep(s, "videoDecoder!!.dequeueOutputBuffer(info, 0)",
            "TextureBridge.dequeueOutput(videoDecoder!!, info, 0)")
    s = rep(s, "videoDecoder!!.releaseOutputBuffer(lastIndex, false)",
            "TextureBridge.releaseBoolean(videoDecoder!!, lastIndex, false)")
    s = rep(s, "videoDecoder!!.releaseOutputBuffer(lastIndex, 0)",
            "TextureBridge.releaseTimed(videoDecoder!!, lastIndex, 0)")
    s = rep(s, "videoDecoder!!.releaseOutputBuffer(lastIndex, System.nanoTime())",
            "TextureBridge.releaseTimed(videoDecoder!!, lastIndex, System.nanoTime())")
    s = rep(s, '                                    handleOutputFormatChanged(videoDecoder!!.outputFormat, "sync")',
            '                                    handleOutputFormatChanged(videoDecoder!!.outputFormat, "sync")\n'
            '                                    TextureBridge.noteOutputFormat(videoDecoder!!, videoDecoder!!.outputFormat)')
    s = rep(s, "decoder.dequeueInputBuffer(5000)",
            "TextureBridge.dequeueInput(decoder, 5000)")
    s = rep(s, "decoder.queueInputBuffer(", "TextureBridge.queueInput(decoder, ", 2)
    s = rep(s,
            "    ): Int {\n        if (stopping || isProcessingPaused) {\n"
            "            // Don't bother if we're stopping or paused",
            "    ): Int {\n        TextureBridge.beginSubmit()\n"
            "        if (stopping || isProcessingPaused) {\n"
            "            // Don't bother if we're stopping or paused")
    for required in ("private fun recordResolutionOutput(codec: MediaCodec",
                     "private fun resolutionFramePresented(codec: MediaCodec",
                     "fun awaitResolutionFrame(width: Int, height: Int",
                     "TextureBridge.configure(videoDecoder!!",
                     "TextureBridge.releaseTimed(videoDecoder!!",
                     "TextureBridge.queueInput(decoder,"):
        if required not in s:
            raise RuntimeError(f"Lost upstream hot switch or SK1 hook: {required}")
    for forbidden in ("videoDecoder!!.configure(format, outSurface, null, 0)",
                      "videoDecoder!!.releaseOutputBuffer(",
                      "videoDecoder!!.dequeueOutputBuffer(",
                      "decoder.queueInputBuffer("):
        if forbidden in s:
            raise RuntimeError(f"Unintercepted SK1 codec call: {forbidden}")
    write(p, s)

def pacing():
    p = "app/src/main/java/com/limelight/binding/video/FramePacingController.kt"
    s = rep(upstream(p), "import com.limelight.BuildConfig\n",
            "import com.limelight.sk1.TextureBridge\nimport com.limelight.BuildConfig\n")
    seen = [0]
    def conv(m: re.Match[str]) -> str:
        seen[0] += 1
        i, value = m.group(1), m.group(2)
        kind = "releaseBoolean" if value.strip() in ("true", "false") else "releaseTimed"
        return f"videoDecoder?.let {{ TextureBridge.{kind}(it, {i}, {value}) }}"
    s = re.sub(r"videoDecoder\?\.releaseOutputBuffer\(([^,\n]+), ([^\n]+)\)", conv, s)
    if seen[0] != 5 or "videoDecoder?.releaseOutputBuffer(" in s:
        raise RuntimeError(f"Expected exactly 5 output pacing hooks, got {seen[0]}")
    write(p, s)

def settings():
    p = "app/src/main/java/com/limelight/preferences/PreferenceConfiguration.kt"
    write(p, rep(upstream(p),
                 "var videoFormat: FormatOption = FormatOption.AUTO",
                 "var videoFormat: FormatOption = FormatOption.FORCE_HEVC"))
    p = "app/src/main/res/xml/preferences.xml"
    s = upstream(p)
    anchor = '<ListPreference\n            android:key="video_format"'
    if s.count(anchor) != 1:
        raise RuntimeError("video_format XML anchor absent or duplicate")
    start = s.index(anchor)
    end = s.index("/>", start)
    e = s[start:end]
    if e.count('android:defaultValue="auto"') != 1:
        raise RuntimeError("video_format default changed upstream")
    s = s[:start] + e.replace('android:defaultValue="auto"',
                             'android:defaultValue="forceh265"') + s[end:]
    write(p, s)
    p = "app/src/main/java/com/limelight/utils/UpdateManager.kt"
    write(p, rep(upstream(p),
                 "    fun checkForUpdatesOnStartup(context: Context) {\n"
                 "        enqueueUpdateCheck(context, showToast = false, enforceStartupInterval = true)\n"
                 "    }",
                 '    @Suppress("UNUSED_PARAMETER")\n'
                 "    fun checkForUpdatesOnStartup(context: Context) {\n"
                 "        // SK1: update checks remain user-initiated only.\n"
                 "    }"))
    p = "app/build.gradle"
    s = rep(upstream(p), 'versionName "12.15.6"',
            'versionName "12.15.7-sk1-hevc-exp1"')
    s = rep(s, 'versionCode = 121506001', 'versionCode = 121507701')
    s = rep(s, 'applicationIdSuffix ".vplus_debug"\n'
            '            resValue "string", "app_label", audioHapticsAppLabel\n'
            '            resValue "string", "app_label_root", audioHapticsAppLabel',
            'applicationIdSuffix ".vplus_sk1merge157"\n'
            '            resValue "string", "app_label", "Moonlight SK1 12.15.7"\n'
            '            resValue "string", "app_label_root", "Moonlight SK1 12.15.7"')
    write(p, s)

def docs():
    p = "docs/SK1_VPLUS_12_15_7_EXPERIMENT.md"
    write(p, """# Ugoos SK1 / Moonlight V+ 12.15.7 / HEVC v14 (experiment 1)

Upstream: qiin2333/moonlight-vplus v12.15.7, commit dd127f20c90ae581bc05fb51a4b0caa960d1ffb2.
Known-good owner-tested rollback: sk1-vplus-12.14.1-beta2-hevc-v14-r1.
Previous experimental release: sk1-vplus-12.14.3-hevc-v14-exp1.

## SK1 preservation contract

- Keep owner-tested v14 TextureBridge.java and HevcGeometry.java exactly unchanged.
- Reattach 21 decoder and 5 frame-pacing bridge hooks; fail build if compiled
  classes differ from the owner-tested 26-call MediaCodec interception baseline.
- Preserve upstream resolution hot switch, stream lifecycle coordinator,
  HDR10 Main10 compatibility fix, new performance HUD and recent UDP core.
- Default HEVC for fresh installs; disable automatic application update checks.
- Isolated package: com.limelight.vplus_sk1merge157. This test coexists with
  SK1 12.14.3 and the owner-tested 12.14.1-beta.2; pairing/settings start fresh.
- System UDP rmem_max of 8 MiB is configured separately via Magisk on the SK1:
  the APK does not change kernel parameters or require root.
- Upstream release tag retains stale 12.15.6 build.gradle versionName;
  this build is explicitly labelled 12.15.7-sk1-hevc-exp1.

## Required hardware validation

1. HEVC 3840x2160 / 60Hz HDR, 100-200 Mbps: 4-7ms decode target and smooth pacing.
2. Stream stop/reconnect, app background/foreground, 1080p -> 4K resolution switch.
3. Confirm 4K decoded frame reaches the expected physical output crop, no surface leaks.
4. Use new HUD to compare Rx/Rd and network loss before investigating AV1.
5. AV1 stutter, visual breakup and recovery remain unsolved: this update is not
   an AV1 fix, even though updated common-c includes network protocol fixes.
""")

def verify_original_sk1():
    p = "app/src/main/java/com/limelight/sk1/TextureBridge.java"
    digest = subprocess.check_output(["git", "hash-object", p]).decode().strip()
    if digest != "853982cd9eccce47d9f905dd89c7d2e6091c8c86":
        raise RuntimeError(f"Original HEVC bridge changed unexpectedly: {digest}")
    geo = Path("app/src/main/java/com/limelight/sk1/HevcGeometry.java").read_text()
    if "public static HevcGeometry inspect" not in geo:
        raise RuntimeError("Original SK1 HEVC geometry source missing")

if __name__ == "__main__":
    verify_original_sk1()
    renderer()
    pacing()
    settings()
    docs()
    print("SK1: pinned upstream V+ 12.15.7 integrated; verified HEVC bridge preserved.")
