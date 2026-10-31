#!/usr/bin/env python3
"""Fail-closed bytecode regression audit for SK1 v14 HEVC bridge integration.

Checks a COMPILED APK, not just whether a TextureBridge.java source file exists.
The owner-tested 12.14.1-beta.2 APK and V+ 12.14.3 experiment 1 were both
independently decoded and shown to have the same 26 required bridge call sites.
This check protects future merges from silently compiling but dropping the fix.
Only Python stdlib is required. No assumptions about external decompilers.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
import struct
import subprocess
import sys
import zipfile


def u16(data: bytes, pos: int) -> int:
    return struct.unpack_from("<H", data, pos)[0]


def u32(data: bytes, pos: int) -> int:
    return struct.unpack_from("<I", data, pos)[0]


def uleb(data: bytes, pos: int) -> tuple[int, int]:
    result = 0
    for shift in range(0, 35, 7):
        char = data[pos]
        pos += 1
        result |= (char & 0x7f) << shift
        if char < 0x80:
            return result, pos
    raise ValueError("Invalid ULEB128 value")


class Dex:
    def __init__(self, data: bytes):
        if data[:4] != b"dex\n":
            raise ValueError("Not an Android DEX")
        self.data = data
        self.strings = []
        count, start = u32(data, 0x38), u32(data, 0x3c)
        for i in range(count):
            pos = u32(data, start + 4 * i)
            _, pos = uleb(data, pos)
            end = data.index(b"\x00", pos)
            self.strings.append(data[pos:end].decode("utf-8", "replace"))
        count, start = u32(data, 0x40), u32(data, 0x44)
        self.types = [self.strings[u32(data, start + 4 * i)] for i in range(count)]
        count, start = u32(data, 0x58), u32(data, 0x5c)
        self.methods = []
        for i in range(count):
            class_idx, _, name_idx = struct.unpack_from("<HHI", data, start + 8 * i)
            self.methods.append((self.types[class_idx], self.strings[name_idx]))

        self.classes = {}
        count, start = u32(data, 0x60), u32(data, 0x64)
        for i in range(count):
            pos = start + 32 * i
            cls = self.types[u32(data, pos)]
            ptr = u32(data, pos + 24)
            if not ptr:
                continue
            sizes = []
            for _ in range(4):
                size, ptr = uleb(data, ptr)
                sizes.append(size)
            for field_count in sizes[:2]:
                for _ in range(field_count):
                    _, ptr = uleb(data, ptr)
                    _, ptr = uleb(data, ptr)
            for method_count in sizes[2:]:
                method_index = 0
                for _ in range(method_count):
                    delta, ptr = uleb(data, ptr)
                    method_index += delta
                    _, ptr = uleb(data, ptr)
                    code_off, ptr = uleb(data, ptr)
                    self.classes.setdefault(cls, []).append(
                        (self.methods[method_index][1], code_off)
                    )

    def calls(self, cls: str):
        for method, code_off in self.classes.get(cls, []):
            if not code_off:
                continue
            insn_count = u32(self.data, code_off + 12)
            insns = self.data[code_off + 16:code_off + 16 + 2 * insn_count]
            # Android invoke-* opcodes put a method_ids index into their
            # second code unit. Filter by resolved destination to exclude data.
            for offset in range(0, len(insns) - 3, 2):
                opcode = insns[offset]
                if opcode not in (0x6e, 0x6f, 0x70, 0x71, 0x72,
                                  0x74, 0x75, 0x76, 0x77, 0x78):
                    continue
                index = u16(insns, offset + 2)
                if index < len(self.methods):
                    dest, name = self.methods[index]
                    yield method, dest, name


EXPECTED_METHODS = Counter({
    "attach": 1,
    "beginSubmit": 1,
    "configure": 1,
    "dequeueInput": 1,
    "dequeueOutput": 2,
    "queueInput": 2,
    "noteOutput": 1,
    "noteOutputFormat": 2,
    "releaseCodec": 4,
    "releaseBoolean": 4,
    "releaseTimed": 7,
})

EXPECTED_CALLERS = Counter({
    "MediaCodecDecoderRenderer": 13,
    "MediaCodecDecoderRenderer$setupAsyncCallback$1": 2,
    "MediaCodecDecoderRenderer$startRendererThread$1": 6,
    "FramePacingController": 5,
})

FORBIDDEN_DIRECT_MEDIA_CALLS = {
    "configure", "releaseOutputBuffer", "release",
    "dequeueOutputBuffer", "dequeueInputBuffer", "queueInputBuffer",
}


def check_sources() -> None:
    for name, expected in (
        ("TextureBridge.java", "853982cd9eccce47d9f905dd89c7d2e6091c8c86"),
        ("HevcGeometry.java", "6b3829af1406538a11114e1c074224b6e45f610d"),
    ):
        path = "app/src/main/java/com/limelight/sk1/" + name
        got = subprocess.check_output(
            ["git", "hash-object", path], text=True
        ).strip()
        if got != expected:
            raise RuntimeError(f"{name} source changed: {got} != {expected}")
    print("PASS: both owner-tested HEVC Java sources are identical")


def check_apk(apk: str) -> None:
    methods = Counter()
    callers = Counter()
    forbidden = []
    definitions = set()

    with zipfile.ZipFile(apk) as z:
        if z.testzip() is not None:
            raise RuntimeError("APK has a corrupt ZIP entry")
        libs = z.namelist()
        if "lib/armeabi-v7a/libmoonlight-core.so" not in libs:
            raise RuntimeError("SK1 stock ARM32 native library is missing")
        for path in libs:
            if not re.fullmatch(r"classes\d*\.dex", path):
                continue
            dex = Dex(z.read(path))
            definitions.update(dex.classes)
            for cls in dex.classes:
                if not (
                    cls.startswith("Lcom/limelight/binding/video/MediaCodecDecoderRenderer")
                    or cls.startswith("Lcom/limelight/binding/video/FramePacingController")
                ):
                    continue
                short = cls.rsplit("/", 1)[-1].removesuffix(";")
                for caller, dest, name in dex.calls(cls):
                    if dest == "Lcom/limelight/sk1/TextureBridge;":
                        methods[name] += 1
                        callers[short] += 1
                    if dest == "Landroid/media/MediaCodec;" and name in FORBIDDEN_DIRECT_MEDIA_CALLS:
                        forbidden.append((short, caller, name))

    for cls in ("Lcom/limelight/sk1/TextureBridge;",
                "Lcom/limelight/sk1/HevcGeometry;",
                "Lcom/limelight/binding/video/ResolutionFrameTracker;"):
        if cls not in definitions:
            raise RuntimeError(f"Missing compiled class: {cls}")
    if methods != EXPECTED_METHODS:
        raise RuntimeError(f"HEVC bridge bytecode calls differ!\nExpected: {EXPECTED_METHODS}\nGot: {methods}")
    if callers != EXPECTED_CALLERS:
        raise RuntimeError(f"HEVC callers differ!\nExpected: {EXPECTED_CALLERS}\nGot: {callers}")
    if forbidden:
        raise RuntimeError(f"Bypass of SK1 bridge: {forbidden}")
    print("PASS: 26/26 compiled HEVC bridge call sites match owner-tested APK")
    print("PASS: frame pacing 5/5 and core decoder 21/21")
    print("PASS: no unwrapped MediaCodec I/O calls in renderer or pacing")
    print("PASS: HEVC source geometry, bridge, new resolution tracker and ARM32 library present")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: sk1-audit-hevc-apk.py <compiled.apk>")
    check_sources()
    check_apk(sys.argv[1])
