# 商品真实素材库

[新手逐步使用指南](USER_GUIDE.md) · [用途与适用人群介绍](INTRODUCTION.md)

`product-real-asset-library` · 独立技能仓库 · MIT

适合：整理供应商产品图、报价表和视频的电商人员

## 解决什么问题

供应商发来一个文件夹，里面图片、视频、报价表混在一起，有重复、有坏图、来源说不清。这个技能把「文件夹」变成「可交差的清单」：有什么、缺什么、哪些重复、每张图的来源和授权状态是什么。

## 快速开始

只需要 Python 3.10+。缩略图额外需要 Pillow。

```sh
# 1. 先用自带示例跑通（合成示例，不是真实商品照片）
python scripts/asset_library.py examples/示例素材 --out ./样例输出

# 2. 换成自己的素材文件夹
python scripts/asset_library.py "D:\素材\榨汁杯" --out "D:\素材\榨汁杯-清单"
```

打开 `./样例输出/素材清单.html` 就能看到缩略图清单。想直接看效果、不想跑代码的，仓库里 `examples/示例输出/` 已附这次运行的真实产物。

## 输入与输出

**输入**：任意素材文件夹（图片 / MP4-MOV-M4V / xlsx / 文档混杂都行），可递归子目录；可选一份授权声明 JSON。

**输出**：

| 文件 | 用途 |
| --- | --- |
| `素材清单.html` | 带缩略图的素材墙 + 重复组 + 缺类别 + 告警 + 限制 |
| `asset-index.json` | 完整索引：每项含 ID、相对路径、类型、推断角色、分辨率、时长、字节、SHA256、探测状态、授权、发布状态、重复于 |
| `素材清单.csv` | 平表，Excel 直接打开（UTF-8 BOM） |
| `thumbs/` | 缩略图，最长边默认 320px |
| `授权与来源-待填.json` | 授权模板：补 `rights` 与 `rights_evidence` 后用 `--rights` 回灌，HOLD → 可复核 |

授权字段取值：`owned`（自有）/ `licensed`（已获授权）/ `public_domain` / `unknown`。除 `unknown` 外还必须有非空 `rights_evidence` 才会变成 `READY_FOR_REVIEW`；`unknown` 或证据为空一律 `HOLD`。

## 参数

| 参数 | 说明 |
| --- | --- |
| `--out` | 必填，输出目录，不存在会自动创建 |
| `--product` | 型号/商品名，只写进结果里，方便多批次区分 |
| `--rights` | 授权声明 JSON（结构同 `授权与来源-待填.json`） |
| `--require` | 必备类别，逗号分隔，默认 `主图,细节图,场景图,视频` |
| `--thumb-px` | 缩略图最长边，默认 320 |
| `--no-thumbs` | 不生成缩略图 |
| `--organize` | 额外按推断角色**复制**一份到 `organized/`，原文件不动 |
| `--path-style relative` | 清单里记相对路径，不外泄本机绝对路径 |
| `--max-files` | 上限保护，默认 5000 |

## 本次完善（0.3.0）

原有缺口：`build_asset_index.py` 要求先手写 manifest，普通用户拿到文件夹后无法一键出结果；没有缩略图；重复标记要手填清单才有。

已补：`scripts/asset_library.py` 一条命令完成扫描 → 指纹 → 查重 → 缩略图 → HTML/CSV/JSON 清单 → 授权模板；未装 Pillow 自动降级；坏图/不支持格式标 ERROR/PARTIAL 不中断整批；重跑会清理上一次的缩略图残留；输出目录在素材目录内部时不会被算进素材。

## 当前限制

- **判重只认字节一致**（SHA256）。相似构图、压缩重存、裁剪过的图不会被判重。
- **来源与授权是声明，不是核验**。工具不联网、不查证版权，`source_verified`/`rights_verified` 恒为 `false`。
- **角色靠文件名关键词猜**，输出标「推断 / 按类型 / UNKNOWN」，可能误判。
- **视频只读 MP4/MOV/M4V 头部**，AVI/MKV/WMV/FLV 时长分辨率标 UNKNOWN；不抽封面帧（未接入 ffmpeg，属未验证能力）。
- HEIC/AVIF/TIFF 等可能读不出分辨率，标 PARTIAL，不等于文件损坏。
- 大文件夹（上万文件）会逐个算 SHA256，耗时随文件总量线性增长。

## 验证与使用注意

```sh
python -m unittest discover -s tests -v
```

30 项测试覆盖：正常文件夹、缺文件夹/给的是文件/空文件夹、无 Pillow 降级、重复运行与缩略图残留清理、授权声明与 SHA 冲突、路径逃逸拒绝、HTML 转义、角色推断等。

测试覆盖的只是离线可断言的行为，不等于真实平台、生产环境或业务效果验证。真实运行结果见 `examples/示例输出/`（合成素材，已去掉本机绝对路径）。

示例素材与「视频」均为程序生成，不是真实商品照片；不要用它们判断清晰度或对外宣传。

## 来源与工作记录

由 miaorrr8888-cloud 在 AI 辅助下积累和维护，来源与边界见 [PROVENANCE.md](PROVENANCE.md)，许可见 [LICENSE](LICENSE)。本版在其公开版本基础上扩展了一键整理入口，署名与许可证保留不变。

[全部独立技能与阶段性工作记录](https://github.com/miaorrr8888-cloud/agent-skills-worklog)

## 旧入口（仍可用）

```sh
python scripts/media_probe.py examples/media --json
python scripts/xlsx_cellimage_map.py examples/demo.xlsx
python scripts/build_asset_index.py examples/asset-ledger.json
```

`examples/demo.xlsx` 是解析用最小 ZIP/XML 夹具，不是可直接填写的 Excel 模板。

## 运行环境

| 项 | 状态 |
|---|---|
| Windows 11 + Python 3.12 / 3.13 | ✅ 实测通过 |
| Linux / macOS | ⚠️ **未实测**。代码用 `pathlib`，无硬编码分隔符，理论上可跑，但测试只在 Windows 跑过，不声称支持 |

诚实标注：没实跑过的平台，不要在对外文案里写「已支持」。
