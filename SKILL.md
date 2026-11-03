---
name: product-real-asset-library
description: 给一个素材文件夹就自动整理商品图片和视频：算指纹、标重复、生成带缩略图的清单，来源与授权未知时如实标 HOLD。
license: MIT
version: "1.1.0"
display_name: "商品真实素材库"
agent_created: true

---
# 商品真实素材库

给一个文件夹，一条命令出「带缩略图的素材清单」。不联网，不上传，不动你的原文件。

## 什么时候用

- 供应商甩来一堆图片视频，要快速看清有什么、缺什么、哪些重复；
- 上架前要交代「这张图哪来的、有没有授权」；
- WPS 报价表里的内嵌图要追到具体产品行。

## 一条命令（主入口）

```sh
python scripts/asset_library.py "<素材文件夹>" --out "<输出文件夹>"
```

Windows 下路径带空格或中文时加引号。跑完看控制台最后几行，或直接打开 `<输出文件夹>/素材清单.html`。

常用变体：

```sh
# 填好授权后再跑一次，HOLD 会变成「可复核」
python scripts/asset_library.py "<素材文件夹>" --out "<输出>" --rights "<输出>/授权与来源-待填.json"

# 额外按推断角色复制一份到 <输出>/organized/（只复制，不移动不删除）
python scripts/asset_library.py "<素材文件夹>" --out "<输出>" --organize

# 清单里记相对路径（便于打包给别人看），不生成缩略图
python scripts/asset_library.py "<素材文件夹>" --out "<输出>" --path-style relative --no-thumbs
```

## 会产出什么

| 文件 | 内容 |
| --- | --- |
| `素材清单.html` | 缩略图素材墙：类型、推断角色、分辨率、时长、大小、SHA256、授权状态、重复标记、缺类别提示、告警与方法限制 |
| `asset-index.json` | 机器可读的完整索引，含 duplicate_groups / warnings / limitations |
| `素材清单.csv` | 给 Excel 看的平表（UTF-8 BOM） |
| `thumbs/*.jpg` | 缩略图（最长边 320px，需 Pillow） |
| `授权与来源-待填.json` | 预先填好文件清单的授权模板，你补 rights 和证据后再 `--rights` 回灌 |

## 必须如实说的三件事

1. **重复只证明字节一致。** 判重基于 SHA256；相似构图、压缩重存、二次裁剪都不会被判为重复。
2. **来源与授权是声明，不是核验。** 工具无法证明版权归属，`source_verified` / `rights_verified` 恒为 `false`。授权未知默认 HOLD，可以内部看，别直接对外投放。
3. **角色是按文件名猜的。** `主图 / 白底图 / 细节图 / 场景图 / 视频` 只靠关键词匹配，输出里标了「推断 / 按类型 / UNKNOWN」。缺哪类就写缺，静态图不能冒充实拍视频。

## 依赖与降级

- 核心整理、查重、清单：**只用 Python 3.10+ 标准库**，装了 Python 就能跑。
- 缩略图：需要 Pillow（`python -m pip install Pillow`）。没装不会崩，会跳过缩略图、在清单里写「未安装 Pillow」，退出码 1。
- 视频封面帧：**未接入 ffmpeg**，视频只有时长与分辨率，不生成封面。用 ffmpeg 抽帧属于未验证功能，不要声称支持。

退出码：`0` 无告警；`1` 有告警（HOLD / 重复 / 缺类别 / 缩略图跳过）；`2` 输入错误（路径不存在、不是文件夹、空文件夹、授权文件非法）。

## 已有脚本（保留，未改动行为）

- `scripts/media_probe.py <路径> [--json]`：单文件/目录的尺寸、时长、SHA256，坏文件标 ERROR/PARTIAL 不中断。
- `scripts/xlsx_cellimage_map.py <book.xlsx> [sheet]`：WPS `DISPIMG` 内嵌图 → 工作表行号 + 产品名 + md5。
- `scripts/build_asset_index.py <manifest.json>`：手工清单式台账（旧入口，仍可用）。

## 上手示例与当前限制

先读 [README.md](README.md) 的快速开始与限制；`examples/示例素材` 是可直接跑的合成示例，`examples/示例输出` 是它的真实运行结果（已去掉本机路径）。不要把合成演示或离线检查当成真实平台验证。

## 面向使用者的说明

解释用途、适用人群、安装与第一次运行时读 [USER_GUIDE.md](USER_GUIDE.md)；中文对外介绍参考 [INTRODUCTION.md](INTRODUCTION.md)，介绍稿不等于已发布。
