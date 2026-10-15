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


def local_name(element):
    return element.tag.split('}')[-1]


def load_strings(z):
    if 'xl/sharedStrings.xml' not in z.namelist(): return []
    root = ET.fromstring(z.read('xl/sharedStrings.xml'))
    return [''.join(n.text or '' for n in si.iter() if local_name(n) == 't')
            for si in root if local_name(si) == 'si']


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
    if 'xl/cellimages.xml' not in z.namelist(): return {}
    relpath = 'xl/_rels/cellimages.xml.rels'
    if relpath not in z.namelist(): return {}
    rels = ET.fromstring(z.read(relpath))
    targets = {r.get('Id'): r.get('Target') for r in rels if r.get('TargetMode') != 'External'}
    root = ET.fromstring(z.read('xl/cellimages.xml'))
    out = {}
    for pic in root.iter():
        if local_name(pic) != 'pic': continue
        name = next((n.get('name') for n in pic.iter() if local_name(n) == 'cNvPr'), None)
        embed = next((value for n in pic.iter() if local_name(n) == 'blip' for key,value in n.attrib.items() if key.split('}')[-1] == 'embed'), None)
        if name and embed in targets: out[name] = resolve_target(targets[embed])
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
        for cell in ET.fromstring(s).iter():
            if local_name(cell) != 'c': continue
            ref = cell.get('r')
            if not ref: continue
            formula = next((n.text or '' for n in cell if local_name(n) == 'f'), '')
            value = next((n.text or '' for n in cell if local_name(n) == 'v'), '')
            if 'DISPIMG' in formula:
                match = re.search(r'DISPIMG\("([^"\s]+)"', formula)
                rows[ref] = {'__img__':match.group(1) if match else '?'}
            elif cell.get('t') == 's':
                try: rows[ref] = strings[int(value)]
                except (ValueError,IndexError): rows[ref] = ''
            elif cell.get('t') == 'inlineStr':
                rows[ref] = ''.join(n.text or '' for n in cell.iter() if local_name(n) == 't')
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
