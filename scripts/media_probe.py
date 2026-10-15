#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""media_probe.py — 无依赖读取图片分辨率 + 视频时长/分辨率 + md5（用于素材去重与溯源）

用法:
    python media_probe.py <dir_or_file> [<dir_or_file> ...]

输出（制表符分隔）:
    分辨率  字节数  md5前10  路径
    视频多一列:  时长秒
"""
import os
import sys
import struct
import hashlib

IMG_EXT = {"png", "jpg", "jpeg", "webp", "bmp", "gif"}
VID_EXT = {"mp4", "mov", "m4v", "avi", "mkv"}


def png_size(p):
    with open(p, "rb") as f:
        d = f.read(33)
    if d[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", d[16:24])


def jpg_size(p):
    with open(p, "rb") as f:
        if f.read(2) != b"\xff\xd8":
            return None
        while True:
            b = f.read(1)
            while b and b != b"\xff":
                b = f.read(1)
            if not b:
                return None
            mk = f.read(1)
            while mk == b"\xff":
                mk = f.read(1)
            if not mk:
                return None
            m = mk[0]
            if m in (0xD8, 0xD9) or 0xD0 <= m <= 0xD7:
                continue
            ln = f.read(2)
            if len(ln) < 2:
                return None
            L = struct.unpack(">H", ln)[0]
            if 0xC0 <= m <= 0xCF and m not in (0xC4, 0xC8, 0xCC):
                d = f.read(5)
                h, w = struct.unpack(">HH", d[1:5])
                return (w, h)
            f.seek(L - 2, 1)


def webp_size(p):
    with open(p, "rb") as f:
        d = f.read(32)
    if len(d) < 30:
        return None
    tag = d[12:16]
    if tag == b"VP8X":
        w = int.from_bytes(d[24:27], "little") + 1
        h = int.from_bytes(d[27:30], "little") + 1
        return (w, h)
    if tag == b"VP8 ":
        w = int.from_bytes(d[26:28], "little") & 0x3FFF
        h = int.from_bytes(d[28:30], "little") & 0x3FFF
        return (w, h)
    if tag == b"VP8L":
        b = int.from_bytes(d[21:25], "little")
        w = (b & 0x3FFF) + 1
        h = ((b >> 14) & 0x3FFF) + 1
        return (w, h)
    return None


def mp4_info(p):
    """返回 (duration_sec, (w,h)) —— 解析 mvhd / tkhd，无需 ffmpeg。"""
    data = open(p, "rb").read()
    dur = None
    wh = None
    i = data.find(b"mvhd")
    if i > 0:
        ver = data[i + 4]
        if ver == 0:
            ts, dv = struct.unpack(">II", data[i + 16:i + 24])
        else:
            ts, dv = struct.unpack(">IQ", data[i + 24:i + 36])
        dur = dv / ts if ts else None
    j = data.find(b"tkhd")
    if j > 0:
        b0 = j - 4
        bs = struct.unpack(">I", data[b0:b0 + 4])[0]
        end = b0 + bs
        w, h = struct.unpack(">II", data[end - 8:end])
        wh = (round(w / 65536.0), round(h / 65536.0))
    return dur, wh


def dims(p, ext):
    try:
        if ext == "png":
            return png_size(p)
        if ext in ("jpg", "jpeg"):
            return jpg_size(p)
        if ext == "webp":
            return webp_size(p)
    except Exception:
        return None
    return None


def main(paths):
    files = []
    for a in paths:
        if os.path.isdir(a):
            for dp, _dn, fn in os.walk(a):
                files += [os.path.join(dp, f) for f in fn]
        elif os.path.exists(a):
            files.append(a)
    files.sort()
    print("RESOLUTION\tDURATION\tBYTES\tMD5_10\tPATH")
    for p in files:
        ext = p.lower().rsplit(".", 1)[-1]
        if ext not in IMG_EXT and ext not in VID_EXT:
            continue
        res, dur = None, ""
        if ext in VID_EXT:
            d, r = mp4_info(p)
            res = r
            dur = f"{d:.2f}" if d else ""
        else:
            res = dims(p, ext)
        try:
            size = os.path.getsize(p)
            h = hashlib.md5(open(p, "rb").read()).hexdigest()[:10]
        except Exception:
            size, h = 0, ""
        r = f"{res[0]}x{res[1]}" if res else "?"
        print(f"{r}\t{dur}\t{size}\t{h}\t{p}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1:])
