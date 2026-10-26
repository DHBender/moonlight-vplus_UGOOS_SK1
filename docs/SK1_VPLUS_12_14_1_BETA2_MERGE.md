# Ugoos SK1 / Moonlight V+ 12.14.1-beta.2 integration

- Base: release/sk1-texture-v14 at 4948db01a13fbc6605fb10b92235284c204693b2.
- Upstream: qiin2333/moonlight-vplus at 866cb83690a602c0a416dcbdf7fe5d598d57b661.
- Upstream changes merged, retaining fork README.md on the sole merge conflict.
- New installations default to HEVC (forceh265) in XML and Kotlin defaults.
- Automatic application update checks on startup are disabled in UpdateManager.
  Manual update-check action is intentionally left available.
- Debug package: com.limelight.vplus_sk1merge, installed alongside tested v14.
- HEVC smoothness is NOT verified by this merge: the released v14 APK was
  uploaded separately, and the v14 Git branch does not contain codec-renderer
  modifications relative to upstream 12.13.3. A source-identical reconstruction
  of that APK has not been established.
- Owner-tested v14 APK and release branch are not modified.
- Verify on the physical Ugoos SK1 before promoting this integration.

Validation: automated build/unit tests where dependencies permit, followed by
on-device HEVC 4K HDR, pacing, crop and input-latency comparison against v14.
