# 桌面公开实验发布 v0.1.1-desktop-experiment

应用版本0.1.1-experiment，日志schema 2。该发布整理已测试test2的启动与页面逻辑，加入维护者日志核验、许可和测试指令修订，不改变岗位样例与排序逻辑。它是合成数据桌面实验，不是可真实求职的完整产品。

## 下载与安装

在GitHub Releases选择v0.1.1-desktop-experiment，下载dagongren-0.1.1-experiment.zip及同名.zip.sha256。该ZIP为白名单打包产物，包含逐文件MANIFEST.json；不要把其校验值用于GitHub自动生成的Source code ZIP。

解压至新目录，使用已有Python 3.10+。Windows双击start-windows.bat；macOS终端执行sh ./start-macos.command。没有Python时只能直接打开web/index.html体验静态页面，不能完成启动器验证。完整命令见desktop-testing.md。

Windows校验：Get-FileHash ./dagongren-0.1.1-experiment.zip -Algorithm SHA256。macOS校验：shasum -a 256 ./dagongren-0.1.1-experiment.zip。与下载的.sha256文件比较后再解压；服务仅监听本机，Ctrl+C停止。

## 已验证范围

- Windows设备：调整配置后的官方Python embeddable 3.12.10与无头Chrome，13项自动化断言通过。
- Intel macOS设备：已有托管Python 3.13.12与无头Chrome，T01–T10通过。
- 两端基础及干净目录检查成功，日志由维护者独立核验，详见test2-validation.md。
- 维护者单机：25项Python回归、JS逻辑检查、版本/链接/隐私扫描、带空格干净目录演练。

未验证Apple Silicon、Safari/Edge/Firefox、人工有头体验、无Python新机器。Windows嵌入式Python须处理其_pth导入限制，不推荐不熟悉Python的用户据此认定开箱可用。端口及停止由自动化验证，不能扩展为所有终端退出行为均验证。

## 内容与边界

6家合成公司；条件分组、排序、选择/取消、隐藏/重置、组内置顶及日志导出。日志审计器仅核验已记录状态一致性；不代表所有测试通过。没有BOSS登录/岗位抓取、真实简历导入、模型、财报适配器或外部投递。

MIT许可见LICENSE。不存在上游三项目代码依赖或官方背书。白名单发布不含原始回传包、真实简历、数据库、浏览器会话、私人目录或凭据。请人工回传合成日志和脱敏问题描述，不自动上传。历史标签不移动；更新main不修改已下载包。
