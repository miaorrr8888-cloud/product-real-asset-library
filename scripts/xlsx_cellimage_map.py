#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""xlsx_cellimage_map.py — 把 xlsx 的"单元格内嵌图"映射到行号，并联动输出该行产品名。

背景：WPS / 部分 Excel 把图片以"单元格内嵌图"保存，单元格里是
      =DISPIMG("ID_xxxx",1) 公式，图片实体在 xl/media/，ID→文件 的映射在
      xl/cellimages.xml + xl/_rels/cellimages.xml.rels。

用法:
    python xlsx_cellimage_map.py <book.xlsx> [sheet_name]

输出（每个含图单元格一行）:
    SHEET  CELL  ROW  产品名(B列)  图片文件  md5前10
另附 "=== 所有内嵌图 ===" 与 "=== CELL→media ===" 便于交叉核对。

实战价值：用哈希把"本地某张图"对回"报价表第几行、哪个型号"，
        从而判断该图属于哪个型号（同系列多型号极易混淆）。
"""
import sys
import posixpath
import re
import zipfile
import hashlib
import xml.etree.ElementTree as ET  # noqa: F401  (保留，便于扩展)


def text_of(si_xml):
    return "".join(ET.fromstring("<root>" + si_xml + "</root>").itertext())


def load_strings(z):
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    ss = z.read("xl/sharedStrings.xml").decode("utf-8", errors="replace")
    return [text_of(x) for x in re.findall(r"<si>(.*?)</si>", ss, re.S)]


def resolve_target(target):
    path = posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join('xl', target))
    if not path.startswith('xl/') or '..' in path.split('/'):
        raise ValueError('relationship outside workbook')
    return path


def sheet_map(z):
    wb = ET.fromstring(z.read('xl/workbook.xml'))
    rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    targets = {r.get('Id'): r.get('Target') for r in rels if r.get('TargetMode') != 'External'}
    ns = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
    return {sheet.get('name'): resolve_target(targets[sheet.get(ns)])
            for sheet in wb.iter() if sheet.tag.split('}')[-1] == 'sheet' and sheet.get(ns) in targets}


def cellimages(z):
    """ID_xxx -> media/imageN.ext"""
    if "xl/cellimages.xml" not in z.namelist():
        return {}
    ci = z.read("xl/cellimages.xml").decode("utf-8", errors="replace")
    rels = z.read("xl/_rels/cellimages.xml.rels").decode("utf-8", errors="replace")
    rid2t = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels))
    out = {}
    for blk in re.findall(r"<xdr:pic>.*?</xdr:pic>", ci, re.S):
        nm = re.search(r'name="([^"]+)"', blk)
        em = re.search(r'r:embed="([^"]+)"', blk)
        if nm and em:
            t = rid2t.get(em.group(1), "?")
            out[nm.group(1)] = t.replace("media/", "xl/media/")
    return out


def col_of(ref):
    return re.match(r"([A-Z]+)", ref).group(1)


def row_of(ref):
    return int(re.search(r"(\d+)", ref).group(1))


def main(book, want_sheet=None):
    z = zipfile.ZipFile(book)
    strings = load_strings(z)
    id2img = cellimages(z)
    sheets = sheet_map(z)

    print("=== 所有内嵌图 (%d) ===" % len(id2img))
    for k, v in id2img.items():
        try:
            h = hashlib.md5(z.read(v)).hexdigest()[:10]
        except Exception:
            h = "?"
        print(f"  {k} -> {v}  md5={h}")

    for name, path in sheets.items():
        if want_sheet and name != want_sheet:
            continue
        if path not in z.namelist():
            continue
        s = z.read(path).decode("utf-8", errors="replace")
        rows = {}
        # 注意：不能用 re.finditer(r'<c r="..".*?</c>') —— 自闭合空单元格
        # （如 <c r="A1" s="5"/>）会让 `(.*?)</c>` 一路吞掉下一个单元格，
        # 导致紧随其后的 B 列等被整列漏掉。改为按 <c r=" 切分，逐格解析。
        for part in re.split(r'(?=<c r=")', s):
            m = re.match(r'<c r="([A-Z]+\d+)"([^>]*?)(/?)>', part)
            if not m:
                continue
            ref, attrs, selfclose = m.group(1), m.group(2), m.group(3)
            body = "" if selfclose else part[m.end():].split("</c>")[0]
            vm = re.search(r"<v>(.*?)</v>", body, re.S)
            if vm and 't="s"' in attrs:
                try:
                    rows[ref] = strings[int(vm.group(1))]
                except Exception:
                    rows[ref] = ""
            elif "DISPIMG" in body:
                f = re.search(r'DISPIMG\(&quot;([^&]+)&quot;', body) or \
                    re.search(r'DISPIMG\("([^"]+)"', body)
                rows[ref] = {"__img__": f.group(1) if f else "?"}
        print(f"\n=== SHEET {name} : 含图单元格 ===")
        for ref, val in sorted(rows.items(), key=lambda kv: (row_of(kv[0]), kv[0])):
            if isinstance(val, dict) and "__img__" in val:
                r = row_of(ref)
                img = id2img.get(val["__img__"], "NOT-FOUND")
                # 同行 B 列 = 通常的产品名
                b = rows.get("B%d" % r, "")
                btxt = b if isinstance(b, str) else ""
                md5 = "?"
                if img in z.namelist():
                    md5 = hashlib.md5(z.read(img)).hexdigest()[:10]
                print(f"  {name}\t{ref}\trow{r}\tB={btxt[:50]}\t{img}\tmd5={md5}")
        del rows


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
