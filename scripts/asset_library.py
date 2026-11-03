#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""asset_library.py —— 一条命令整理商品素材文件夹。

用法:
    python scripts/asset_library.py <素材文件夹> --out <输出目录>
    python scripts/asset_library.py <素材文件夹> --out <输出目录> --rights 授权.json
    python scripts/asset_library.py <素材文件夹> --out <输出目录> --organize
    python scripts/asset_library.py <素材文件夹> --out <输出目录> --path-style relative --no-thumbs

做什么:
  1. 递归扫描文件夹（跳过符号链接与缓存目录），逐文件算 SHA256、尺寸、时长；
  2. 按 SHA256 标记重复文件（同字节），其余复制为“归档副本”只在 --organize 时才做；
  3. 用 Pillow 生成缩略图（未安装则跳过并在清单里写明），输出 HTML 素材墙 + CSV + JSON；
  4. 来源/授权默认 UNKNOWN → 发布状态 HOLD；可用 --rights 传入声明后转为 READY_FOR_REVIEW；
  5. 生成一份待填写的授权与来源模板，下次填好再跑一次即可。

不做:
  * 不联网、不上传任何文件；
  * 不移动、不删除、不改名原文件；
  * 不判断图片内容真伪，不识别型号，不证明版权归属；
  * 不把“声明”当成“已核实”（source_verified / rights_verified 恒为 False）。

退出码: 0=全部可复核且无告警; 1=有告警(HOLD/重复/缺图/缩略图跳过); 2=输入错误。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import importlib.util
import json
import os
import re
import shutil
import struct
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

VERSION = "0.3.1"
TOOL = "asset_library.py"

IMAGE_EXT = {"png", "jpg", "jpeg", "webp", "bmp", "gif", "tif", "tiff", "heic", "heif", "avif"}
VIDEO_EXT = {"mp4", "mov", "m4v", "avi", "mkv", "wmv", "flv"}
TABLE_EXT = {"xlsx", "xlsm", "xls", "csv", "tsv"}
DOC_EXT = {"pdf", "doc", "docx", "ppt", "pptx", "txt", "md"}
AUDIO_EXT = {"mp3", "wav", "m4a", "aac", "flac"}

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".idea", ".vscode", ".cache"}
RIGHTS_VALUES = {"owned", "licensed", "public_domain", "unknown"}
RIGHTS_LABEL = {
    "owned": "自有素材",
    "licensed": "已获授权",
    "public_domain": "公共领域",
    "unknown": "未知（默认 HOLD）",
}

# 角色推断：只按文件名关键词猜，输出里一律标注“推断”，不是识别结论。
# 顺序即优先级，首个命中即返回。因此“主图”必须排在“白底图”之前：
# 电商最常见的命名是“白底主图”，它指的正是白底版主图，不能因为先匹配到“白底”
# 就把主图算成缺失（v0.3.0 及以前会误报“缺主图”，v0.3.1 修正）。
# 另：序号类关键词（01）过于宽泛，会把“细节图_01”抢成主图，因此单独降级为兜底规则。
ROLE_RULES = [
    ("检测报告/资质", ("检测", "质检", "报告", "证书", "认证", "report", "cert", "test-report")),
    ("尺寸/参数图", ("尺寸", "参数", "规格", "size", "dim", "spec", "measure")),
    ("主图", ("主图", "首图", "封面", "main", "hero", "cover")),
    ("白底图", ("白底", "white", "-bd", "_bd")),
    ("细节图", ("细节", "局部", "特写", "detail", "closeup", "close-up", "macro")),
    ("场景图", ("场景", "实拍", "使用", "lifestyle", "scene", "context", "usage")),
    ("包装图", ("包装", "外箱", "盒子", "package", "packing", "box")),
    ("视频", ("视频", "展示视频", "video", "demo", "clip")),
]

# 兜底：图片名里只有序号且为 01 时，按主图处理（原规则里的 “01” 关键词）。
MAIN_INDEX_FALLBACK = re.compile(r"(?:^|[^0-9])0*1(?:[^0-9]|$)")

REQUIRED_ROLES_DEFAULT = ["主图", "细节图", "场景图", "视频"]

# 覆盖率别名：白底图在主流平台上就是主图位，不该因为叫“白底”就报缺主图。
# 只影响“必备类别是否覆盖”的统计，不改写素材自身的角色标签。
ROLE_ALIASES = {"白底图": "主图"}
LIMITATIONS = [
    "只按文件名字符串推断素材角色，可能误判；改名后请以人工核对为准。",
    "重复判定仅基于 SHA256 逐字节一致；相似构图、压缩后重存、二次裁剪都不会被判为重复。",
    "来源与授权来自你填写的声明，工具不会、也无法核验版权归属；source_verified / rights_verified 恒为 false。",
    "图片尺寸/格式靠头部解析；HEIC/AVIF/TIFF 等可能读不出尺寸，会标 PARTIAL，不等于文件损坏。",
    "视频只读 MP4/MOV/M4V 头部；AVI/MKV/WMV/FLV 的时长与分辨率标 UNKNOWN。",
    "不生成视频封面帧（需要 ffmpeg，本版未接入），视频在清单里显示时长与分辨率占位。",
    "缩略图需要 Pillow；未安装时不生成图片，只输出带原图相对路径的清单。",
    "缩略图是降采样副本，不能用于判断清晰度或印刷质量；上架请用原图。",
]


def say(text: str = "") -> None:
    """控制台编码可能是 GBK，不能编码的字符用 ? 代替而不是崩掉。"""
    try:
        print(text)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(text.encode(enc, "replace").decode(enc, "replace"))


def load_media_probe():
    """复用同目录的 media_probe.py（同包内脚本，非第三方依赖）。"""
    path = Path(__file__).resolve().parent / "media_probe.py"
    spec = importlib.util.spec_from_file_location("_pral_media_probe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------- 扫描与探测

def kind_of(ext: str) -> str:
    if ext in IMAGE_EXT:
        return "图片"
    if ext in VIDEO_EXT:
        return "视频"
    if ext in TABLE_EXT:
        return "表格"
    if ext in DOC_EXT:
        return "文档"
    if ext in AUDIO_EXT:
        return "音频"
    return "其他"


def infer_role(name: str, kind: str) -> tuple[str, str]:
    # 视频/表格/文档先按类型定性，避免文件名里的“使用”“主图”等词把它带偏。
    if kind == "视频":
        return "视频", "按类型"
    if kind in {"表格", "文档", "音频"}:
        return "其他", "按类型"
    low = name.lower()
    for role, keys in ROLE_RULES:
        if any(k in low for k in keys):
            return role, "推断"
    # 兜底：只有序号 01 的图片按主图处理（放在最后，避免抢走“细节图_01”这类命名）。
    if kind == "图片" and MAIN_INDEX_FALLBACK.search(low):
        return "主图", "推断"
    if kind == "图片":
        return "未归类图片", "UNKNOWN"
    return "其他", "UNKNOWN"


def scan_folder(root: Path, exclude: list[Path]) -> list[Path]:
    files: list[Path] = []
    excluded = {p.resolve() for p in exclude if p}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        here = Path(dirpath)
        dirnames[:] = sorted(
            d for d in dirnames
            if d.lower() not in SKIP_DIRS and not (here / d).is_symlink()
            and (here / d).resolve() not in excluded
        )
        for name in sorted(filenames):
            p = here / name
            if p.is_symlink() or not p.is_file():
                continue
            if p.resolve() in excluded:
                continue
            files.append(p)
    return files


def probe(path: Path, probe_mod, root: Path, path_style: str) -> dict:
    info = probe_mod.inspect(path)
    ext = path.suffix.lower().lstrip(".")
    kind = kind_of(ext)
    rel = path.relative_to(root).as_posix()
    shown = rel if path_style == "relative" else str(path)
    role, role_conf = infer_role(path.name, kind)
    resolution = info.get("resolution")
    duration = info.get("duration")
    probe_status = info.get("status")
    if kind not in ("图片", "视频"):
        # 表格/文档/音频不走媒体头解析，不是“坏文件”，标 N/A 免得被误读成异常。
        probe_status = "N/A"
    return {
        "id": None,
        "file": shown,
        "rel_path": rel,
        "name": path.name,
        "ext": ext,
        "kind": kind,
        "role": role,
        "role_source": role_conf,
        "bytes": info.get("bytes"),
        "sha256": info.get("sha256"),
        "md5_10": info.get("md5_10"),
        "resolution": list(resolution) if resolution else None,
        "duration": round(duration, 2) if isinstance(duration, (int, float)) else None,
        "probe_status": probe_status,
        "probe_error": info.get("error"),
        "source_url": None,
        "rights": "unknown",
        "rights_evidence": None,
        "rights_verified": False,
        "source_verified": False,
        "release_status": "HOLD",
        "duplicate_of": None,
        "duplicate_count": 0,
        "thumbnail": None,
        "thumbnail_status": "PENDING",
    }


# ---------------------------------------------------------------- 重复与角色

def mark_duplicates(assets: list[dict]) -> tuple[list[dict], list[dict]]:
    groups: dict[str, list[dict]] = {}
    for a in assets:
        if a["sha256"]:
            groups.setdefault(a["sha256"], []).append(a)
    dup_groups = []
    for sha, items in groups.items():
        if len(items) < 2:
            continue
        items.sort(key=lambda x: x["rel_path"].casefold())
        keeper = items[0]
        keeper["duplicate_count"] = len(items) - 1
        for other in items[1:]:
            other["duplicate_of"] = keeper["rel_path"]
        dup_groups.append({
            "sha256": sha,
            "keep": keeper["rel_path"],
            "duplicates": [x["rel_path"] for x in items[1:]],
            "bytes_each": keeper["bytes"],
            "redundant_bytes": (keeper["bytes"] or 0) * (len(items) - 1),
        })
    dup_groups.sort(key=lambda g: -g["redundant_bytes"])
    return assets, dup_groups


def roles_present(assets: list[dict], required: list[str]) -> tuple[list[str], list[str]]:
    have = {a["role"] for a in assets if not a["duplicate_of"]}
    # 白底图按别名计入主图覆盖率；只影响统计，不改写素材自身的角色标签。
    have |= {ROLE_ALIASES[r] for r in list(have) if r in ROLE_ALIASES}
    covered = [r for r in required if r in have]
    missing = [r for r in required if r not in have]
    return covered, missing


# ---------------------------------------------------------------- 缩略图

def pillow_available() -> bool:
    try:
        import PIL  # noqa: F401
        return True
    except Exception:
        return False


def make_thumbnail(src: Path, dst: Path, max_px: int) -> tuple[str, str | None]:
    try:
        from PIL import Image, ImageOps
    except Exception:
        return "SKIPPED_NO_PILLOW", "未安装 Pillow"
    try:
        with Image.open(src) as im:
            im.seek(0)
            im = ImageOps.exif_transpose(im)
            if im.mode in ("RGBA", "LA", "P"):
                im = im.convert("RGBA")
                bg = Image.new("RGB", im.size, (255, 255, 255))
                bg.paste(im, mask=im.split()[-1])
                im = bg
            else:
                im = im.convert("RGB")
            im.thumbnail((max_px, max_px), Image.LANCZOS)
            dst.parent.mkdir(parents=True, exist_ok=True)
            im.save(dst, "JPEG", quality=80, optimize=True)
        return "OK", None
    except Exception as exc:  # 坏图/格式不支持 → 记录后继续
        return "FAILED", type(exc).__name__


def safe_thumb_name(idx: int, name: str, sha: str | None) -> str:
    stem = Path(name).stem
    stem = unicodedata.normalize("NFKD", stem)
    stem = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff._-]+", "-", stem).strip("-._") or "asset"
    stem = stem[:32]
    return f"{idx:03d}-{stem}-{(sha or 'nohash')[:8]}.jpg"


# ---------------------------------------------------------------- 授权声明

def load_rights(path: Path, root: Path) -> tuple[dict, list[str]]:
    """读取 --rights 声明；规则与 build_asset_index.py 保持一致。"""
    from urllib.parse import urlsplit

    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or not isinstance(data.get("assets"), list):
        raise ValueError("--rights 文件必须是 {\"assets\": [...]} 结构")
    out: dict[str, dict] = {}
    warnings: list[str] = []
    for entry in data["assets"]:
        if not isinstance(entry, dict):
            raise ValueError("assets 元素必须是对象")
        rel = entry.get("file")
        if not isinstance(rel, str) or not rel.strip():
            raise ValueError("assets[].file 必须是非空文本")
        rel_norm = rel.replace("\\", "/").lstrip("./")
        rights = entry.get("rights", "unknown")
        if rights not in RIGHTS_VALUES:
            raise ValueError(f"rights 非法: {rights}")
        source = entry.get("source_url")
        if source:
            u = urlsplit(str(source))
            if u.scheme != "https" or not u.hostname or u.username or u.password:
                raise ValueError(f"source_url 必须是 https 且不含账号信息: {source}")
        evidence = entry.get("rights_evidence")
        out[rel_norm] = {
            "rights": rights,
            "source_url": source,
            "rights_evidence": evidence,
            "declared_sha256": entry.get("sha256"),
        }
    return out, warnings


def apply_rights(assets: list[dict], rights_map: dict, warnings: list[str]) -> None:
    matched = set()
    for a in assets:
        entry = rights_map.get(a["rel_path"])
        if not entry:
            continue
        matched.add(a["rel_path"])
        a["rights"] = entry["rights"]
        a["source_url"] = entry["source_url"]
        a["rights_evidence"] = entry["rights_evidence"]
        declared = entry.get("declared_sha256")
        if entry["rights"] != "unknown" and isinstance(entry["rights_evidence"], str) and entry["rights_evidence"].strip():
            a["release_status"] = "READY_FOR_REVIEW"
        if declared and a["sha256"] and declared != a["sha256"]:
            warnings.append(f"声明 SHA256 与实测不一致：{a['rel_path']}（文件可能已被替换）")
    for rel in sorted(set(rights_map) - matched):
        warnings.append(f"授权声明里的文件在素材文件夹中不存在：{rel}")


# ---------------------------------------------------------------- 输出

def build_index(assets, dup_groups, root, options, warnings, covered, missing,
                thumb_stats) -> dict:
    total_bytes = sum(a["bytes"] or 0 for a in assets)
    redundant = sum(g["redundant_bytes"] for g in dup_groups)
    ready = sum(1 for a in assets if a["release_status"] == "READY_FOR_REVIEW")
    return {
        "tool": TOOL,
        "version": VERSION,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_root": "." if options["path_style"] == "relative" else str(root),
        "path_style": options["path_style"],
        "options": options,
        "summary": {
            "file_count": len(assets),
            "total_bytes": total_bytes,
            "unique_hashes": len({a["sha256"] for a in assets if a["sha256"]}),
            "duplicate_files": sum(a["duplicate_count"] for a in assets if not a["duplicate_of"]),
            "duplicate_groups": len(dup_groups),
            "redundant_bytes": redundant,
            "ready_for_review": ready,
            "hold": len(assets) - ready,
            "by_kind": {k: sum(1 for a in assets if a["kind"] == k)
                        for k in sorted({a["kind"] for a in assets})},
            "probe_not_ok": sum(1 for a in assets if a["probe_status"] not in ("OK", "N/A")),
            "thumbnails": thumb_stats,
        },
        "roles_required": options["require_roles"],
        "roles_covered": covered,
        "roles_missing": missing,
        "assets": assets,
        "duplicate_groups": dup_groups,
        "warnings": warnings,
        "limitations": LIMITATIONS,
        "notice": "来源与授权为使用者声明，非法律核验；重复仅证明字节一致。",
    }


def fmt_bytes(n) -> str:
    if not isinstance(n, int) or n < 0:
        return "未知"
    if n < 1024:
        return f"{n} B"
    value = float(n)
    for unit in ("KB", "MB", "GB"):
        value /= 1024.0
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}"
    return f"{value:.1f} GB"


def esc(x) -> str:
    return html.escape("" if x is None else str(x))


def render_html(index: dict) -> str:
    s = index["summary"]
    rows = index["assets"]
    dup_ids = {a["rel_path"] for a in rows if a["duplicate_of"]}
    cards = []
    for a in rows:
        badges = [f'<span class="b kind">{esc(a["kind"])}</span>']
        if a["duplicate_of"]:
            badges.append('<span class="b dup" title="与保留件字节一致">重复</span>')
        elif a["duplicate_count"]:
            badges.append(f'<span class="b keep">保留件 · 另 {a["duplicate_count"]} 份相同</span>')
        if a["release_status"] == "READY_FOR_REVIEW":
            badges.append('<span class="b ready">可复核</span>')
        else:
            badges.append('<span class="b hold">HOLD</span>')
        badges.append(f'<span class="b rights">{esc(RIGHTS_LABEL.get(a["rights"], a["rights"]))}</span>')
        if a["probe_status"] not in ("OK", "N/A"):
            badges.append(f'<span class="b err">{esc(a["probe_status"])}</span>')

        res = f'{a["resolution"][0]}×{a["resolution"][1]}' if a["resolution"] else "分辨率 UNKNOWN"
        dur = f'{a["duration"]}s' if a["duration"] is not None else ""
        if a["thumbnail"]:
            thumb = f'<img src="{esc(a["thumbnail"])}" alt="{esc(a["name"])}" loading="lazy">'
        else:
            note = {
                "SKIPPED_NO_PILLOW": "缩略图未生成（未安装 Pillow）",
                "FAILED": "缩略图生成失败",
                "SKIPPED_NON_IMAGE": "非图片，无缩略图",
            }.get(a["thumbnail_status"], "无缩略图")
            thumb = f'<div class="ph"><span>{esc(note)}</span></div>'
        extra = []
        if a["duplicate_of"]:
            extra.append(f'<p class="mini">与 <code>{esc(a["duplicate_of"])}</code> 字节一致</p>')
        if a["source_url"]:
            extra.append(f'<p class="mini">来源：<code>{esc(a["source_url"])}</code></p>')
        if a["rights_evidence"]:
            extra.append(f'<p class="mini">授权说明：{esc(a["rights_evidence"])}</p>')
        if a["probe_error"]:
            extra.append(f'<p class="mini">探测错误：{esc(a["probe_error"])}</p>')
        cards.append(f"""
      <figure class="card{' isdup' if a['duplicate_of'] else ''}">
        <div class="shot">{thumb}</div>
        <figcaption>
          <div class="fn" title="{esc(a["rel_path"])}">{esc(a["name"])}</div>
          <div class="badges">{''.join(badges)}</div>
          <p class="mini">{esc(a["role"])} · {esc(a["role_source"])}　{res}　{dur}　{esc(fmt_bytes(a["bytes"]))}</p>
          <p class="mini sha">SHA256 {esc((a["sha256"] or "未知")[:12])}…</p>
          {''.join(extra)}
        </figcaption>
      </figure>""")

    dup_rows = "".join(
        f"<tr><td><code>{esc(g['keep'])}</code></td><td>{''.join(f'<code>{esc(d)}</code><br>' for d in g['duplicates'])}</td>"
        f"<td>{esc(fmt_bytes(g['redundant_bytes']))}</td></tr>"
        for g in index["duplicate_groups"]) or '<tr><td colspan="3">没有逐字节相同的文件。</td></tr>'

    miss = index["roles_missing"]
    miss_block = ('<p class="warn">按文件名推断，以下必备类别没有找到（可能未拍或未命名）：'
                  + '、'.join(f"<b>{esc(m)}</b>" for m in miss)
                  + '。缺就是缺，静态图不能冒充实拍视频。</p>') if miss else \
                 '<p class="ok">必备类别按文件名推断均已出现（仍需人工确认内容对不对）。</p>'

    warn_block = ''.join(f"<li>{esc(w)}</li>" for w in index["warnings"]) or "<li>无告警。</li>"
    limit_block = ''.join(f"<li>{esc(x)}</li>" for x in index["limitations"])

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>素材清单 · {esc(index['source_root'])}</title>
<style>
  :root {{ --ink:#111827; --sub:#4b5563; --line:#e5e7eb; --bg:#f8fafc; --card:#fff;
           --hold:#b45309; --ready:#047857; --dup:#7c3aed; --err:#b91c1c; --kind:#1d4ed8; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; padding:28px 20px 64px; background:var(--bg); color:var(--ink);
          font:15px/1.65 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif; }}
  .wrap {{ max-width:1180px; margin:0 auto; }}
  h1 {{ font-size:26px; margin:0 0 6px; }}
  h2 {{ font-size:18px; margin:34px 0 12px; padding-bottom:8px; border-bottom:1px solid var(--line); }}
  .meta {{ color:var(--sub); font-size:13px; }}
  .stats {{ display:flex; flex-wrap:wrap; gap:10px; margin:18px 0 6px; }}
  .stat {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:10px 16px; min-width:118px; }}
  .stat b {{ display:block; font-size:22px; }}
  .stat span {{ color:var(--sub); font-size:12px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(228px,1fr)); gap:14px; }}
  .card {{ margin:0; background:var(--card); border:1px solid var(--line); border-radius:14px; overflow:hidden; }}
  .card.isdup {{ border-style:dashed; border-color:#c4b5fd; }}
  .shot {{ aspect-ratio:1/1; background:#f1f5f9; display:flex; align-items:center; justify-content:center; overflow:hidden; }}
  .shot img {{ width:100%; height:100%; object-fit:contain; }}
  .ph {{ color:#94a3b8; font-size:12px; text-align:center; padding:12px; }}
  figcaption {{ padding:10px 12px 12px; }}
  .fn {{ font-weight:600; font-size:13px; word-break:break-all; }}
  .badges {{ display:flex; flex-wrap:wrap; gap:5px; margin:6px 0; }}
  .b {{ font-size:11px; padding:1px 7px; border-radius:999px; border:1px solid currentColor; }}
  .b.kind {{ color:var(--kind); }} .b.hold {{ color:var(--hold); }} .b.ready {{ color:var(--ready); }}
  .b.dup {{ color:var(--dup); }} .b.err {{ color:var(--err); }} .b.rights {{ color:#374151; }}
  .b.keep {{ color:var(--ready); }}
  .mini {{ margin:2px 0 0; font-size:12px; color:var(--sub); word-break:break-all; }}
  .sha {{ font-family:ui-monospace,Consolas,monospace; }}
  code {{ background:#f1f5f9; padding:0 4px; border-radius:4px; font-size:12px; }}
  table {{ width:100%; border-collapse:collapse; background:var(--card); border:1px solid var(--line); border-radius:12px; overflow:hidden; }}
  th,td {{ text-align:left; padding:9px 12px; border-bottom:1px solid var(--line); font-size:13px; vertical-align:top; }}
  th {{ background:#f8fafc; color:var(--sub); font-weight:600; }}
  ul {{ margin:8px 0; padding-left:22px; }} li {{ margin:4px 0; }}
  .warn {{ background:#fffbeb; border:1px solid #fcd34d; color:#92400e; padding:10px 14px; border-radius:10px; }}
  .ok {{ background:#ecfdf5; border:1px solid #6ee7b7; color:#065f46; padding:10px 14px; border-radius:10px; }}
  .note {{ background:#fff; border:1px solid var(--line); border-radius:12px; padding:12px 16px; color:var(--sub); font-size:13px; }}
</style></head>
<body><div class="wrap">
  <h1>素材清单</h1>
  <p class="meta">来源目录：<code>{esc(index['source_root'])}</code>　生成时间：{esc(index['generated_at'])}　工具：{esc(TOOL)} v{esc(VERSION)}</p>
  <div class="stats">
    <div class="stat"><b>{s['file_count']}</b><span>文件</span></div>
    <div class="stat"><b>{s['unique_hashes']}</b><span>唯一指纹</span></div>
    <div class="stat"><b>{s['duplicate_files']}</b><span>重复文件</span></div>
    <div class="stat"><b>{esc(fmt_bytes(s['total_bytes']))}</b><span>总大小</span></div>
    <div class="stat"><b>{esc(fmt_bytes(s['redundant_bytes']))}</b><span>重复占用</span></div>
    <div class="stat"><b>{s['ready_for_review']}</b><span>可复核</span></div>
    <div class="stat"><b>{s['hold']}</b><span>HOLD</span></div>
    <div class="stat"><b>{s['thumbnails'].get('ok',0)}</b><span>缩略图</span></div>
  </div>
  <p class="note">{esc(index['notice'])}　授权值为“未知”的素材一律 HOLD：可以内部查看，不建议直接对外投放。</p>

  <h2>必备类别检查</h2>
  {miss_block}
  <p class="meta">本次要求类别：{esc('、'.join(index['roles_required']))}　已覆盖：{esc('、'.join(index['roles_covered']) or '无')}</p>

  <h2>素材墙（{len(rows)} 项）</h2>
  <div class="grid">{''.join(cards)}</div>

  <h2>重复组（{len(index['duplicate_groups'])} 组）</h2>
  <table><thead><tr><th>保留件</th><th>重复件</th><th>可回收</th></tr></thead><tbody>{dup_rows}</tbody></table>

  <h2>告警</h2><ul>{warn_block}</ul>
  <h2>方法与限制</h2><ul>{limit_block}</ul>
  <p class="meta">本文件不联网生成；缩略图是降采样副本，上架请用原图。</p>
</div></body></html>
"""


def write_csv(path: Path, assets: list[dict]) -> None:
    cols = ["rel_path", "kind", "role", "role_source", "resolution", "duration", "bytes",
            "sha256", "probe_status", "rights", "release_status", "duplicate_of", "source_url"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["文件", "类型", "推断角色", "角色来源", "分辨率", "时长秒", "字节",
                    "SHA256", "探测状态", "授权", "发布状态", "重复于", "来源网址"])
        for a in assets:
            res = f'{a["resolution"][0]}x{a["resolution"][1]}' if a["resolution"] else "UNKNOWN"
            w.writerow([a["rel_path"], a["kind"], a["role"], a["role_source"], res,
                        a["duration"] if a["duration"] is not None else "UNKNOWN",
                        a["bytes"], a["sha256"], a["probe_status"], a["rights"],
                        a["release_status"], a["duplicate_of"] or "", a["source_url"] or ""])


def write_rights_template(path: Path, assets: list[dict]) -> None:
    payload = {
        "_说明": "把 rights 改成 owned/licensed/public_domain 并填 rights_evidence（如“供应商微信授权截图 2026-10-01”）后，用 --rights 指向本文件再跑一次。rights 仍为 unknown 的项会保持 HOLD。",
        "assets": [
            {"file": a["rel_path"], "sha256": a["sha256"], "rights": "unknown",
             "source_url": None, "rights_evidence": None}
            for a in assets
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def organize_copies(assets: list[dict], root: Path, out_dir: Path) -> tuple[int, list[str]]:
    """把素材按推断角色复制到 <out>/organized/。只复制，不移动、不删除、不改名。"""
    copied, notes = 0, []
    for a in assets:
        if a["duplicate_of"]:
            continue
        src = root / a["rel_path"]
        dst_dir = out_dir / "organized" / a["role"]
        dst = dst_dir / src.name
        dst_dir.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            notes.append(f"目标已存在，跳过复制：{a['rel_path']}")
            continue
        shutil.copy2(src, dst)
        copied += 1
    return copied, notes


# ---------------------------------------------------------------- 主流程

def run(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="整理商品素材文件夹：查重、生成缩略图清单、登记来源授权。不联网。")
    parser.add_argument("folder", help="素材文件夹")
    parser.add_argument("--out", required=True, help="输出目录（不存在会自动创建）")
    parser.add_argument("--product", default=None, help="型号或商品名，仅记录到结果里")
    parser.add_argument("--rights", default=None, help="授权与来源声明 JSON（见生成的待填模板）")
    parser.add_argument("--require", default=None,
                        help="必备类别，逗号分隔；默认 主图,细节图,场景图,视频")
    parser.add_argument("--thumb-px", type=int, default=320, help="缩略图最长边，默认 320")
    parser.add_argument("--no-thumbs", action="store_true", help="不生成缩略图")
    parser.add_argument("--organize", action="store_true", help="额外按推断角色复制一份到 out/organized/")
    parser.add_argument("--path-style", choices=["absolute", "relative"], default="absolute",
                        help="清单里记录绝对路径还是相对素材目录的路径")
    parser.add_argument("--max-files", type=int, default=5000, help="上限保护，默认 5000")
    args = parser.parse_args(argv)

    root = Path(args.folder).expanduser()
    if not root.exists():
        say(f"[错误] 素材文件夹不存在：{root}")
        return 2
    if not root.is_dir():
        say(f"[错误] 这不是文件夹：{root}")
        return 2
    root = root.resolve()
    out_dir = Path(args.out).expanduser().resolve()

    warnings: list[str] = []
    files = scan_folder(root, [out_dir])
    if not files:
        say(f"[错误] 文件夹里没有可整理的文件：{root}")
        return 2
    if len(files) > args.max_files:
        say(f"[错误] 文件数 {len(files)} 超过上限 {args.max_files}，请分批处理或用 --max-files 提高上限。")
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)
    thumbs_dir = out_dir / "thumbs"
    if thumbs_dir.exists():
        shutil.rmtree(thumbs_dir)  # 只清理自己生成缩略图目录，避免上次残留
    thumbs_dir.mkdir(parents=True)

    probe_mod = load_media_probe()
    assets = [probe(p, probe_mod, root, args.path_style) for p in files]
    for i, a in enumerate(assets, 1):
        a["id"] = f"A{i:03d}"
    assets, dup_groups = mark_duplicates(assets)

    # 缩略图
    have_pillow = pillow_available() and not args.no_thumbs
    thumb_stats = {"ok": 0, "failed": 0, "skipped_no_pillow": 0, "skipped_non_image": 0, "disabled": 0}
    for a in assets:
        if args.no_thumbs:
            a["thumbnail_status"] = "DISABLED"
            thumb_stats["disabled"] += 1
            continue
        if a["kind"] != "图片":
            a["thumbnail_status"] = "SKIPPED_NON_IMAGE"
            thumb_stats["skipped_non_image"] += 1
            continue
        if not have_pillow:
            a["thumbnail_status"] = "SKIPPED_NO_PILLOW"
            thumb_stats["skipped_no_pillow"] += 1
            continue
        name = safe_thumb_name(int(a["id"][1:]), a["name"], a["sha256"])
        status, err = make_thumbnail(root / a["rel_path"], thumbs_dir / name, args.thumb_px)
        a["thumbnail_status"] = status
        if status == "OK":
            a["thumbnail"] = f"thumbs/{name}"
            thumb_stats["ok"] += 1
        else:
            a["thumbnail_status"] = "FAILED"
            thumb_stats["failed"] += 1
            warnings.append(f"缩略图生成失败：{a['rel_path']}（{err}）")

    if not args.no_thumbs and not have_pillow:
        warnings.append("未安装 Pillow，本次没有生成缩略图；需要缩略图请先执行 python -m pip install Pillow")
    if not args.no_thumbs:
        warnings.append("视频封面帧未生成（本版未接入 ffmpeg），视频在清单里只有时长与分辨率。")

    # 授权
    if args.rights:
        try:
            rights_map, rw = load_rights(Path(args.rights).expanduser(), root)
            warnings.extend(rw)
            apply_rights(assets, rights_map, warnings)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            say(f"[错误] 授权文件无法使用：{exc}")
            return 2
    else:
        warnings.append("未提供授权声明：全部素材为 HOLD（可内部查看，不建议直接对外投放）。")

    require = [x.strip() for x in (args.require or ",".join(REQUIRED_ROLES_DEFAULT)).split(",") if x.strip()]
    covered, missing = roles_present(assets, require)
    if missing:
        warnings.append("缺少必备类别（按文件名推断）：" + "、".join(missing))

    bad_probe = [a["rel_path"] for a in assets if a["probe_status"] in ("ERROR", "PARTIAL")]
    if bad_probe:
        head = "、".join(bad_probe[:3]) + ("…" if len(bad_probe) > 3 else "")
        warnings.append(f"{len(bad_probe)} 个媒体文件读不出尺寸或时长（已标 ERROR/PARTIAL，可能损坏或格式不在支持范围）：{head}")

    options = {
        "product": args.product,
        "thumb_px": args.thumb_px,
        "thumbs": not args.no_thumbs,
        "rights_file": str(Path(args.rights).name) if args.rights else None,
        "organize": bool(args.organize),
        "path_style": args.path_style,
        "require_roles": require,
    }
    index = build_index(assets, dup_groups, root, options, warnings, covered, missing, thumb_stats)

    json_path = out_dir / "asset-index.json"
    html_path = out_dir / "素材清单.html"
    csv_path = out_dir / "素材清单.csv"
    rights_path = out_dir / "授权与来源-待填.json"

    json_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    html_path.write_text(render_html(index), encoding="utf-8")
    write_csv(csv_path, assets)
    if not args.rights:
        write_rights_template(rights_path, assets)

    if args.organize:
        copied, notes = organize_copies(assets, root, out_dir)
        warnings.extend(notes)
        say(f"[整理] 已复制 {copied} 个文件到 {out_dir / 'organized'}（原文件未移动、未删除）")

    say("=" * 58)
    say(f"素材文件夹：{root}")
    say(f"文件 {len(assets)} 个｜唯一指纹 {index['summary']['unique_hashes']}｜重复 {index['summary']['duplicate_files']} 个"
        f"（可回收 {fmt_bytes(index['summary']['redundant_bytes'])}）")
    say(f"可复核 {index['summary']['ready_for_review']}｜HOLD {index['summary']['hold']}｜缩略图 {thumb_stats['ok']}")
    if missing:
        say(f"缺类别：{'、'.join(missing)}（按文件名推断）")
    for w in warnings[:8]:
        say(f"! {w}")
    if len(warnings) > 8:
        say(f"! 另有 {len(warnings) - 8} 条告警，见清单 HTML 的“告警”一节。")
    say(f"清单：{html_path}")
    say(f"数据：{json_path}")
    say(f"表格：{csv_path}")
    if not args.rights:
        say(f"待填授权：{rights_path}")
    say("=" * 58)

    exit_code = 0
    if index["summary"]["hold"] > 0:
        exit_code = 1
    if dup_groups or missing or warnings or thumb_stats["failed"] or thumb_stats["skipped_no_pillow"]:
        exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(run())
