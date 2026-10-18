# APK v14: verified bytecode changes (v13 -> v14)

**Source of evidence:** uploaded \`Moonlight-SK1-Texture-v13-direct-noautoupdate.apk\` and \`Moonlight-SK1-Texture-v14-crop-test-noautoupdate.apk\`. Their APK contents were compared by ZIP entry and DEX method descriptors. This page records **binary evidence**, not a reconstructed original Git history.

## Verified binary delta

- File sizes are identical: **37,916,510 bytes**. SHA-256 differs.
- Only these ZIP entry contents differ: \`AndroidManifest.xml\`, \`classes3.dex\`, \`classes5.dex\`, \`META-INF/MANIFEST.MF\`, \`META-INF/SK1TEXTU.SF\`, and \`META-INF/SK1TEXTU.RSA\`. The last three are signature metadata.
- All other APK entries, including \`classes.dex\`, \`classes2.dex\`, \`classes4.dex\`, XML layout resources, and native libraries, are unchanged.
- \`classes5.dex\` grew from **27,812** to **34,428** uncompressed bytes. Five class descriptors were added: \`HevcGeometry\`, \`HevcGeometry$Bits\`, and three compiler-generated synthetic lambda classes.
- \`classes3.dex\` grew from **10,864,620** to **10,864,660** bytes. In particular, \`MediaCodecDecoderRenderer$setupAsyncCallback$1.onOutputFormatChanged()\` now calls \`TextureBridge.noteOutputFormat(codec, format)\`. This is a confirmed new functional call, not merely an index shift.

Raw DEX instruction bytes across thousands of methods differ because DEX reference indexes can be renumbered by a compiler. **Do not equate raw byte differences to thousands of semantic code changes.** Comparison focuses on added class/method references, actual new methods, and control-flow insertion.

## Identified v14 behavior

1. **HEVC SPS geometry:** new \`HevcGeometry.inspect()\` scans Annex-B NAL units for SPS type 33 and parses conformance-window crop. It retains both coded dimensions and visible dimensions, e.g. 3840×2176 coded / 3840×2160 visible.
2. **Source geometry capture:** \`TextureBridge.queueInput()\` gains a call to \`inspectSourceGeometry()\` on codec-config packets, so dimensions are captured from the input bitstream.
3. **Output geometry:** \`TextureBridge.noteOutputFormat()\` reads \`MediaFormat\` width/height and \`crop-left/right/top/bottom\`, and schedules crop correction.
4. **SurfaceControl transactions:** \`applyCropSurface(SurfaceView)\` gets a \`SurfaceControl\` and uses \`SurfaceControl.Transaction.setCrop()\` and \`setScale()\`. This path is guarded for Android API >=33 and has a specific condition for coded 3840×2176, visible 3840×2160, bottom=16.
5. **Lifetime management:** \`releaseCodec()\` resets the crop state and removes layout listeners to avoid stale surface transformations.

**Important nuance:** v13 already includes the \`TextureBridge\` path, including rendering-related MediaCodec interception. v14 adds **geometry correction** to that path. It is not accurate to attribute the entire smooth 4K HDR experience solely to the new crop logic without a controlled A/B test.

## Independent parser reconstruction

- \`research/sk1-v14/HevcGeometry.java\` is a clean-room reference implementation, **not the original v14 source** and **not wired into the production Android application**.
- \`research/sk1-v14/HevcGeometryTest.java\` tests 3840×2176 -> 3840×2160, uncropped 1080p, and invalid buffer bounds.
- Tested separately against the **real HEVC clip bundled inside the uploaded HWPLAY4 test APK**; its SPS declares **1920×1088 coded with an 8-pixel bottom crop, yielding 1920×1080 visible**.

Run locally with a JDK:

\`\`\`sh
mkdir -p /tmp/sk1-java
javac -d /tmp/sk1-java research/sk1-v14/HevcGeometry.java research/sk1-v14/HevcGeometryTest.java
java -cp /tmp/sk1-java com.limelight.sk1.HevcGeometryTest
\`\`\`

The GitHub Actions workflow \`SK1 v14 HEVC geometry verification\` runs the regression test independently of the Android SDK.

## Binary provenance and GPLv3 limitation

The uploaded APK was signed with \`CN=SK1 Texture Diagnostic\`; v13 and v14 certificate fingerprints match. The v14 APK SHA-256:

\`\`\`text
aea9fb5a6661c90b6dccee462498026eb8310b51e55d9558ae7656020226eedf
\`\`\`

The checked-in research Java file alone **cannot reproduce the uploaded v14 APK**. For a GPLv3 public binary release, preserve and publish the complete corresponding source tree, original v14 modifications to Moonlight V+, build scripts, and instructions. Do not present either the earlier TextureView PR or the standalone parser as the complete corresponding source of v14.

**Owner-confirmed device result:** HEVC streaming at 4K HDR on Ugoos SK1 is smooth with subjectively very low latency. No independently measured latency figure is claimed.
