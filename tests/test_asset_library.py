# -*- coding: utf-8 -*-
"""asset_library.py 的回归测试：真实跑一遍文件夹整理，检查产物内容而不只是文件存在。"""
import importlib.util
import json
import shutil
import struct
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    spec = importlib.util.spec_from_file_location("asset_library_under_test", ROOT / "scripts" / "asset_library.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def have_pillow():
    try:
        import PIL  # noqa: F401
        return True
    except Exception:
        return False


def tiny_png(path: Path, size=(64, 48), color=(220, 230, 240)):
    from PIL import Image
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path)
    return path


def fake_mp4(path: Path, seconds=2.0, size=(320, 240)):
    def atom(name, data):
        return struct.pack(">I4s", len(data) + 8, name) + data
    mvhd = atom(b"mvhd", bytes(4) + bytes(8) + struct.pack(">II", 1000, int(seconds * 1000)) + bytes(80))
    tkhd = atom(b"tkhd", bytes(4) + bytes(8) + bytes(64) + struct.pack(">II", size[0] * 65536, size[1] * 65536))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(atom(b"moov", mvhd + atom(b"trak", tkhd)) + atom(b"mdat", b"\0" * 32))
    return path


@unittest.skipUnless(have_pillow(), "需要 Pillow 生成测试图片")
class EndToEnd(unittest.TestCase):
    def setUp(self):
        self.mod = load()
        self.tmp = Path(tempfile.mkdtemp())
        self.src = self.tmp / "素材"
        tiny_png(self.src / "主图" / "杯_主图_01.png", (80, 60))
        tiny_png(self.src / "细节" / "杯_细节图_杯盖.png", (70, 70), (240, 240, 240))
        tiny_png(self.src / "场景" / "杯_场景图.png", (90, 70), (230, 235, 245))
        fake_mp4(self.src / "视频" / "杯_使用展示视频.mp4")
        (self.src / "报价表.txt").write_text("demo", encoding="utf-8")
        self.dup = self.src / "副本" / "IMG_0001.png"
        self.dup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.src / "主图" / "杯_主图_01.png", self.dup)
        self.out = self.tmp / "输出"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def index(self):
        return json.loads((self.out / "asset-index.json").read_text(encoding="utf-8"))

    def test_normal_run_produces_index_html_csv_thumbs(self):
        code = self.mod.run([str(self.src), "--out", str(self.out), "--product", "测试杯"])
        self.assertEqual(code, 1, "默认无授权声明 → 应返回 1")
        data = self.index()
        self.assertEqual(data["summary"]["file_count"], 6)
        self.assertEqual(data["summary"]["duplicate_files"], 1)
        self.assertEqual(data["summary"]["unique_hashes"], 5)
        self.assertEqual(data["summary"]["hold"], 6)
        self.assertEqual(data["roles_missing"], [])
        dup = [a for a in data["assets"] if a["duplicate_of"]]
        self.assertEqual(len(dup), 1)
        self.assertIn(dup[0]["rel_path"], ("副本/IMG_0001.png",))
        self.assertTrue((self.out / "素材清单.html").stat().st_size > 3000)
        self.assertTrue((self.out / "素材清单.csv").read_text(encoding="utf-8-sig").startswith("文件,类型"))
        thumbs = list((self.out / "thumbs").glob("*.jpg"))
        self.assertEqual(len(thumbs), 4, "4 张图片各生成 1 张缩略图（含重复件）")
        self.assertEqual(data["summary"]["thumbnails"]["ok"], 4)
        for a in data["assets"]:
            if a["kind"] == "图片":
                self.assertTrue((self.out / a["thumbnail"]).exists(), a["rel_path"])

    def test_html_escapes_names_and_marks_hold(self):
        weird = self.src / "主图" / "A&B_主图_01.png"
        tiny_png(weird, (60, 60))
        self.mod.run([str(self.src), "--out", str(self.out)])
        html = (self.out / "素材清单.html").read_text(encoding="utf-8")
        self.assertNotIn("A&B_主图_01.png", html, "文件名里的 & 必须转义")
        self.assertIn("A&amp;B_主图_01.png", html)
        self.assertIn("HOLD", html)
        self.assertIn("方法与限制", html)

    def test_missing_category_is_reported(self):
        code = self.mod.run([str(self.src), "--out", str(self.out), "--require", "主图,包装图"])
        self.assertEqual(code, 1)
        self.assertEqual(self.index()["roles_missing"], ["包装图"])

    def test_rerun_is_stable_and_cleans_stale_thumbs(self):
        self.mod.run([str(self.src), "--out", str(self.out)])
        first = self.index()
        self.mod.run([str(self.src), "--out", str(self.out)])
        second = self.index()
        self.assertEqual(first["summary"]["file_count"], second["summary"]["file_count"])
        self.assertEqual(len(list((self.out / "thumbs").glob("*.jpg"))), 4)
        # 删掉一张源图后重跑：不应残留旧缩略图
        (self.src / "细节" / "杯_细节图_杯盖.png").unlink()
        self.mod.run([str(self.src), "--out", str(self.out)])
        self.assertEqual(self.index()["summary"]["file_count"], 5)
        self.assertEqual(len(list((self.out / "thumbs").glob("*.jpg"))), 3)

    def test_rights_manifest_moves_ready_and_flags_sha_mismatch(self):
        self.mod.run([str(self.src), "--out", self.out if False else str(self.out)])
        template = json.loads((self.out / "授权与来源-待填.json").read_text(encoding="utf-8"))
        for entry in template["assets"]:
            if entry["file"] == "主图/杯_主图_01.png":
                entry.update(rights="owned", rights_evidence="自有拍摄")
            if entry["file"] == "场景/杯_场景图.png":
                entry.update(rights="licensed", rights_evidence="供应商邮件 2026-10-01",
                             source_url="https://example.com/license")
            if entry["file"] == "副本/IMG_0001.png":
                entry["sha256"] = "0" * 64  # 故意写错，应产生冲突告警
        manifest = self.tmp / "rights.json"
        manifest.write_text(json.dumps(template, ensure_ascii=False), encoding="utf-8")
        code = self.mod.run([str(self.src), "--out", str(self.out), "--rights", str(manifest)])
        data = self.index()
        ready = [a["rel_path"] for a in data["assets"] if a["release_status"] == "READY_FOR_REVIEW"]
        self.assertEqual(sorted(ready), ["主图/杯_主图_01.png", "场景/杯_场景图.png"])
        self.assertTrue(any("SHA256" in w for w in data["warnings"]))
        self.assertTrue(all(a["rights_verified"] is False for a in data["assets"]))
        self.assertEqual(code, 1)

    def test_bad_rights_url_rejected(self):
        bad = self.tmp / "bad.json"
        bad.write_text(json.dumps({"assets": [{"file": "主图/杯_主图_01.png", "rights": "licensed",
                                              "rights_evidence": "x", "source_url": "http://user:pw@example.com/a"}]}),
                       encoding="utf-8")
        self.assertEqual(self.mod.run([str(self.src), "--out", str(self.out), "--rights", str(bad)]), 2)

    def test_organize_copies_and_never_moves(self):
        code = self.mod.run([str(self.src), "--out", str(self.out), "--organize"])
        self.assertEqual(code, 1)
        self.assertTrue((self.src / "主图" / "杯_主图_01.png").exists(), "原文件必须还在")
        organized = sorted(p.name for p in (self.out / "organized").rglob("*") if p.is_file())
        self.assertIn("杯_主图_01.png", organized)
        self.assertNotIn("IMG_0001.png", organized, "重复件不参与归档复制")
        code2 = self.mod.run([str(self.src), "--out", str(self.out), "--organize"])
        self.assertEqual(code2, 1, "重复运行不应因目标已存在而失败")

    def test_relative_path_style_leaks_no_absolute_path(self):
        self.mod.run([str(self.src), "--out", str(self.out), "--path-style", "relative"])
        raw = (self.out / "asset-index.json").read_text(encoding="utf-8")
        self.assertNotIn(str(self.tmp).replace("\\", "\\\\"), raw)
        data = json.loads(raw)
        self.assertEqual(data["source_root"], ".")
        self.assertTrue(all(not a["file"].startswith("/") and ":" not in a["file"] for a in data["assets"]))

    def test_out_dir_inside_source_is_not_indexed(self):
        out = self.src / "_清单输出"
        self.mod.run([str(self.src), "--out", str(out)])
        self.mod.run([str(self.src), "--out", str(out)])
        data = json.loads((out / "asset-index.json").read_text(encoding="utf-8"))
        self.assertEqual(data["summary"]["file_count"], 6, "输出目录不能把自己算进素材")
        self.assertFalse(any("_清单输出" in a["rel_path"] for a in data["assets"]))


class DegradedAndErrors(unittest.TestCase):
    def setUp(self):
        self.mod = load()
        self.tmp = Path(tempfile.mkdtemp())
        self.src = self.tmp / "素材"
        self.src.mkdir()
        (self.src / "说明.txt").write_text("x", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_missing_folder_exits_2(self):
        self.assertEqual(self.mod.run([str(self.tmp / "没有这个"), "--out", str(self.tmp / "o")]), 2)

    def test_file_instead_of_folder_exits_2(self):
        self.assertEqual(self.mod.run([str(self.src / "说明.txt"), "--out", str(self.tmp / "o")]), 2)

    def test_empty_folder_exits_2(self):
        empty = self.tmp / "空"
        empty.mkdir()
        self.assertEqual(self.mod.run([str(empty), "--out", str(self.tmp / "o")]), 2)

    def test_without_pillow_degrades_instead_of_crashing(self):
        original = self.mod.pillow_available
        self.mod.pillow_available = lambda: False
        try:
            if have_pillow():
                tiny_png(self.src / "图.png")
            code = self.mod.run([str(self.src), "--out", str(self.tmp / "o")])
        finally:
            self.mod.pillow_available = original
        self.assertEqual(code, 1)
        data = json.loads((self.tmp / "o" / "asset-index.json").read_text(encoding="utf-8"))
        self.assertEqual(data["summary"]["thumbnails"]["ok"], 0)
        self.assertTrue(any("Pillow" in w for w in data["warnings"]))
        html = (self.tmp / "o" / "素材清单.html").read_text(encoding="utf-8")
        self.assertIn("未安装 Pillow", html)

    def test_no_thumbs_flag(self):
        code = self.mod.run([str(self.src), "--out", str(self.tmp / "o"), "--no-thumbs"])
        self.assertEqual(code, 1)
        self.assertEqual(list((self.tmp / "o").glob("thumbs/*")), [])


class RoleAndHelpers(unittest.TestCase):
    def setUp(self):
        self.mod = load()

    def test_video_role_not_hijacked_by_other_keywords(self):
        self.assertEqual(self.mod.infer_role("榨汁杯_使用展示视频.mp4", "视频")[0], "视频")
        self.assertEqual(self.mod.infer_role("主图视频.mp4", "视频")[0], "视频")

    def test_image_roles(self):
        cases = {
            "杯_主图_01.jpg": "主图",
            "杯_白底图.png": "白底图",
            "杯_细节图_杯盖.jpg": "细节图",
            "杯_场景图_厨房.jpg": "场景图",
            "杯_尺寸参数图.jpg": "尺寸/参数图",
            "IMG_2043.jpg": "未归类图片",
        }
        for name, role in cases.items():
            self.assertEqual(self.mod.infer_role(name, "图片")[0], role, name)

    def test_baidi_main_image_is_main_not_baidi(self):
        """回归：v0.3.0 把「白底主图」抢成白底图，导致误报缺主图。"""
        for name in ("保温杯_白底主图_01.jpg", "杯_白底主图.png", "主图_白底.jpg", "杯_主图白底.jpg"):
            self.assertEqual(self.mod.infer_role(name, "图片")[0], "主图", name)

    def test_index_fallback_does_not_steal_other_roles(self):
        """序号 01 只能是兜底，不能把「细节图_01」抢成主图。"""
        self.assertEqual(self.mod.infer_role("杯_细节图_01.jpg", "图片")[0], "细节图")
        self.assertEqual(self.mod.infer_role("杯_场景图_01.jpg", "图片")[0], "场景图")
        self.assertEqual(self.mod.infer_role("IMG_01.jpg", "图片")[0], "主图")
        self.assertEqual(self.mod.infer_role("IMG_0001.jpg", "图片")[0], "主图")

    def test_baidi_role_covers_main_requirement(self):
        """只有白底图的文件夹不应报缺主图（白底图就是平台的主图位）。"""
        assets = [{"role": "白底图", "duplicate_of": None}]
        covered, missing = self.mod.roles_present(assets, ["主图"])
        self.assertEqual(covered, ["主图"])
        self.assertEqual(missing, [])
        # 但素材自身的角色标签不能被改写
        self.assertEqual(assets[0]["role"], "白底图")

    def test_missing_main_still_reported_when_truly_absent(self):
        assets = [{"role": "细节图", "duplicate_of": None}]
        covered, missing = self.mod.roles_present(assets, ["主图", "细节图"])
        self.assertEqual(covered, ["细节图"])
        self.assertEqual(missing, ["主图"])

    def test_fmt_bytes(self):
        self.assertEqual(self.mod.fmt_bytes(900), "900 B")
        self.assertEqual(self.mod.fmt_bytes(1536), "1.5 KB")
        self.assertEqual(self.mod.fmt_bytes(None), "未知")

    def test_thumb_name_is_filesystem_safe(self):
        name = self.mod.safe_thumb_name(7, "a/b:c*?.jpg", "abcdef123456")
        self.assertTrue(name.startswith("007-"))
        self.assertTrue(name.endswith(".jpg"))
        self.assertNotIn("/", name)
        self.assertNotIn(":", name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
