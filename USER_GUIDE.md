# 商品真实素材库：用户使用指南

## 它能帮你做什么

把一个乱糟糟的素材文件夹，变成一份能直接交差、能直接看的清单：有缩略图、有重复标记、有缺项提示、有来源和授权状态。

## 适合谁

管理供应商产品图、报价表和视频的商家、采购人员、电商运营。

## 具体解决什么问题

- 不知道这个文件夹里到底有什么、哪些是重复的；
- 供应商给的图不知道能不能用、授权到哪一步了；
- 上架前没人能说清「还缺白底图还是缺视频」；
- WPS 报价表里一堆内嵌图，对不上是哪个型号。

**不适合这些目标：** 自动认出产品型号、证明图片版权、完整解码所有视频格式、兼容所有 Excel 嵌图方式。

## 下载与准备

解压后，打开包含 `SKILL.md`、`README.md`、`USER_GUIDE.md` 的那一层文件夹。不要停在外层目录，也不要只复制一个脚本。

在 Windows 上建议用 Python 3.12（本指南验证环境），在该文件夹打开 PowerShell：

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip install Pillow
```

`Pillow` 只用于生成缩略图。不装也能跑，但清单里没有缩略图。

## 第一次使用：先跑自带示例

```powershell
.\.venv\Scripts\python.exe scripts/asset_library.py examples/示例素材 --out ./样例输出
```

正常输出（退出码 1 是预期的，因为示例没有授权信息）：

```text
文件 6 个｜唯一指纹 5｜重复 1 个（可回收 3.2 KB）
可复核 0｜HOLD 6｜缩略图 4
! 未提供授权声明：全部素材为 HOLD（可内部查看，不建议直接对外投放）。
```

然后打开 `样例输出/素材清单.html`。你会看到：6 张卡片、1 个紫色「重复」标记、1 组重复说明、4 张缩略图、以及「必备类别检查」全部通过。

不想跑也能看：`examples/示例输出/` 就是这次运行的真实产物。

## 换成自己的素材

```powershell
.\.venv\Scripts\python.exe scripts/asset_library.py "D:\素材\榨汁杯" --out "D:\素材\榨汁杯-清单" --product "榨汁杯 JZ-200"
```

第一次跑完，先打开 `D:\素材\榨汁杯-清单\素材清单.html` 核对：

1. 缩略图对不对得上型号（防止混入别的款）；
2. 重复组里的「保留件」是不是你要留的那份；
3. 「必备类别检查」缺什么——缺就补拍或找供应商要，别用静态图冒充视频。

## 补授权，把 HOLD 变成可复核

1. 打开输出目录里的 `授权与来源-待填.json`；
2. 每项把 `rights` 改成 `owned` / `licensed` / `public_domain`，并在 `rights_evidence` 写清楚证据（例：`供应商微信授权截图 2026-10-01`）；有原始页面就填 `source_url`（必须 https）；
3. 存回原路径，再跑一次：

```powershell
.\.venv\Scripts\python.exe scripts/asset_library.py "D:\素材\榨汁杯" --out "D:\素材\榨汁杯-清单" --rights "D:\素材\榨汁杯-清单\授权与来源-待填.json"
```

清单里对应项会变成「可复核」。注意：**这只是把你的声明记录下来**，工具不会去查版权，也不代表法律上没问题。

## 只想按类别归档一份

```powershell
.\.venv\Scripts\python.exe scripts/asset_library.py "D:\素材\榨汁杯" --out "D:\素材\榨汁杯-清单" --organize
```

会在 `榨汁杯-清单\organized\主图\...` 之类目录里**复制**一份，原文件不动、不删、不改名。重复件不参与复制。

## 不想手动敲命令：给AI助手的任务

```text
请只在我选定的素材文件夹和输出文件夹内操作，先用 scripts/asset_library.py 生成清单，
再打开 素材清单.html 告诉我：有哪些重复、缺哪些必备类别、哪些是 HOLD。
然后列出需要我补的授权证据清单。不要联网、不要上传我的素材、不要声称图片版权已被确认，
不要把合成示例当成真实商品照片。
```

## 常见问题

**文件标 PARTIAL 或 ERROR**
先用图片查看器或播放器确认文件是否正常，再检查是否属于支持格式（视频仅 MP4/MOV/M4V 读头）。

**素材被标 HOLD**
看 `rights` 和 `rights_evidence` 是否缺失。填了也要人工复核，不能随手写「已授权」。

**没有缩略图**
没装 Pillow，或用了 `--no-thumbs`。装：`python -m pip install Pillow`。

**找不到文件或脚本**
确认终端当前目录就是含 `SKILL.md` 的那层；路径含空格或中文时加双引号。

**重跑会覆盖上次结果吗**
会覆盖同名清单与缩略图目录（这是为了让结果和当前文件夹一致）；`organized/` 里已存在的文件会跳过不覆盖。

## 当前能力边界

- 判重只认 SHA256 字节一致；相似图不算重复。
- 来源与授权是输入声明，工具不核验版权。
- 角色按文件名关键词推断，标「推断 / 按类型 / UNKNOWN」，会误判。
- 视频不抽封面帧（未接入 ffmpeg）；AVI/MKV 只统计文件本身。
- `examples/demo.xlsx` 是解析用最小夹具，不是可填写的 Excel 模板。

## 验证范围

本指南示例已在 Windows 11 + Python 3.13 的独立副本中实际运行（见 `examples/示例输出`）。macOS / Linux 未验证。WorkBuddy 内的对话调用只在本次交付环境中跑过，未做市场审核。
