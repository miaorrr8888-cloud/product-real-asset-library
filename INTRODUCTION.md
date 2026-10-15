# 产品素材整理与来源台账

目录里文件重复、图片来源没记、同一报价表的图片与产品行容易混淆。

这个开源技能可以帮助你：读取常见图片尺寸与部分视频头信息，计算文件指纹；登记来源与授权证据，标出重复素材；辅助解析部分WPS报价表嵌图。

**适合谁：**管理供应商产品图、报价表和视频的商家、采购人员、电商运营。

**怎么开始：**下载并解压独立仓库，按USER_GUIDE先跑自带示例，再换成自己的资料。需要电脑和相应运行环境。

**能看到的结果：**第一条输出文件尺寸、字节数、SHA256等信息；第二条输出素材记录。示例授权未知，因此 release_status=HOLD 是正常结果。

**使用前知道：**核心脚本只读支持格式的信息。MP4/MOV/M4V主要读头，AVI/MKV未覆盖；来源和授权是输入声明。examples/demo.xlsx 是解析用最小测试夹具，不是可直接填写的完整Excel模板。

[项目与下载入口](https://github.com/miaorrr8888-cloud/product-real-asset-library) · [逐步使用指南](https://github.com/miaorrr8888-cloud/product-real-asset-library/blob/main/USER_GUIDE.md)

说明：示例、演示与实际业务结果分开记录；介绍文案已准备，尚未发布到自媒体平台。
