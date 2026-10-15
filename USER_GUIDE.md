# 产品素材整理与来源台账：用户使用指南

## 它能帮你做什么

读取常见图片尺寸与部分视频头信息，计算文件指纹；登记来源与授权证据，标出重复素材；辅助解析部分WPS报价表嵌图。

## 适合谁

管理供应商产品图、报价表和视频的商家、采购人员、电商运营。

## 具体解决什么问题

目录里文件重复、图片来源没记、同一报价表的图片与产品行容易混淆。

**不适合这些目标：**自动认出所有产品型号、证明图片版权、完整解码所有视频格式或兼容所有Excel嵌图方式。

## 下载与准备

- [打开独立仓库](https://github.com/miaorrr8888-cloud/product-real-asset-library)
- [直接下载源码ZIP](https://github.com/miaorrr8888-cloud/product-real-asset-library/archive/refs/heads/main.zip)

也可在仓库页面点 Code → Download ZIP。解压后打开包含 SKILL.md、README.md、USER_GUIDE.md 的那层文件夹。不要停在外层目录或只复制一个脚本。

建议使用Windows电脑和Python 3.12；这是本次验证环境。先在该文件夹打开PowerShell，再执行：

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe --version
```

这里直接使用虚拟环境里的Python，不需要运行激活脚本或修改系统执行策略。安装步骤及其他系统说明见[通用安装说明](https://github.com/miaorrr8888-cloud/agent-skills-worklog/blob/main/INSTALLATION.md)。

本指南的基础示例只用Python标准库，无需安装第三方Python包。

## 第一次使用：先跑自带示例

先读取一张演示图片的信息，再生成素材台账；授权信息缺失时保留HOLD，不假装可放心发布。

```powershell
.\.venv\Scripts\python.exe scripts/media_probe.py examples/media --json
.\.venv\Scripts\python.exe scripts/build_asset_index.py examples/asset-ledger.json
```

## 结果怎么看

第一条输出文件尺寸、字节数、SHA256等信息；第二条输出素材记录。示例授权未知，因此 release_status=HOLD 是正常结果。

## 换成自己的资料

图片/支持的视频文件或目录；台账JSON中的 assets 数组，每项含 file，可填写 source_url、rights、rights_evidence。文件须在台账文件所在目录内。

先复制少量自己的素材到独立工作目录，再为它们写一份台账；来源不明就写 unknown。确认小样可读后再处理更多文件。

## 不想手动敲命令：给AI助手的任务

以下任务适用于能读取所选目录、执行本地命令的助手。WorkBuddy需要先确认当前版本的权限与技能启用状态；本项目未完成WorkBuddy实际导入验收。

```text
请先读取我选定文件夹中的 SKILL.md 和 USER_GUIDE.md，只在该项目范围内处理。
用自带素材先生成文件索引和授权台账，解释尺寸、SHA256、重复项与HOLD。随后告诉我怎样用自己的文件副本替换示例。不要推断素材是官方图片或自动声称版权已确认。
缺少依赖时先说明用途，优先放进本项目虚拟环境；不要读取其他目录中的密码、密钥或浏览器登录数据。
```

## 常见问题

**文件标 PARTIAL 或 ERROR**

先用播放器或图片查看器确认文件是否正常，再检查是否属于支持格式。

**素材被标HOLD**

查看 rights 和 rights_evidence 是否缺失；填入真实证据后仍应人工复核，不能随意填“已授权”。

**找不到文件或脚本**

确认终端当前目录就是包含SKILL.md的技能根目录；路径含空格时加双引号。输出目录已存在时换新名字，不覆盖已有结果。

## 当前能力边界

核心脚本只读支持格式的信息。MP4/MOV/M4V主要读头，AVI/MKV未覆盖；来源和授权是输入声明。examples/demo.xlsx 是解析用最小测试夹具，不是可直接填写的完整Excel模板。

## 验证范围

本指南示例已在Windows独立副本中运行复核，见[命令复核结果](https://github.com/miaorrr8888-cloud/agent-skills-worklog/blob/main/USER_GUIDES_VERIFICATION.md)。已有回归测试只覆盖被测试行为，不证明真实业务结果。WorkBuddy实际运行、手机端使用和所有系统版本均不在本次已验证范围内。

许可证和素材来源分别见 [LICENSE](LICENSE)、[PROVENANCE.md](PROVENANCE.md)。
