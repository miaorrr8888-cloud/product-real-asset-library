# 产品真实素材索引工具

`product-real-asset-library` · 独立技能仓库 · MIT

适合：整理供应商产品图、报价表和视频的电商人员

## 解决什么问题

查清文件尺寸和时长，追溯 WPS 报价表的内嵌图对应哪个产品行，减少错型号混用。

## 快速开始

核心脚本只需 Python 3.10+ 标准库；开发测试用 Pillow 生成媒体夹具。

在本仓库根目录运行：

```sh
python scripts/media_probe.py examples/media --json
python scripts/xlsx_cellimage_map.py examples/demo.xlsx
```

## 输入与输出

**输入**：图片或 MP4/MOV/M4V 文件/目录；WPS DISPIMG 风格 XLSX。示例是合成演示文件。

**输出**：JSON/TSV 媒体索引，含 SHA256、尺寸、时长、状态；XLSX 输出工作表、单元格、产品名称、图片路径和指纹。

## 本次完善

原有缺口：视频读入整文件，坏媒体可能打断批量任务；XML 命名空间和属性顺序仍可能导致漏图。

已补：改成流式哈希和有边界的 MP4 头读取；坏文件保留 PARTIAL/ERROR 并继续；支持更多常见图片；图片关系和单元格改用 XML 解析。

## 仍然缺什么

不是完整媒体解码器：MP4/MOV/M4V 只读头信息，不支持 AVI/MKV 元数据；WPS DISPIMG 以外的所有嵌图变体未覆盖；哈希和报价表位置不能证明官方来源或版权。

## 验证与使用注意

```sh
python -m unittest discover -s tests -v
```

测试覆盖被断言的离线行为，不等于真实平台、生产模型或业务效果验证。

运行开发测试前安装 Pillow：`python -m pip install Pillow`；核心命令不依赖 Pillow。

示例数据和图片均为合成演示，不是真实客户、交易、销量或模型成绩。不要提交真实凭据和私有输入。

## 来源与工作记录

由 miaorrr8888-cloud 在 AI 辅助下积累和维护，来源与边界见 [PROVENANCE.md](PROVENANCE.md)，许可见 [LICENSE](LICENSE)。

[全部独立技能与阶段性工作记录](https://github.com/miaorrr8888-cloud/agent-skills-worklog)
