# 跨设备部署与回传指令（固定快照）

目标仓库DDHKai/dagongren-qiuzhi，测试标签 **v0.1.1-test2**；应用内版本仍为 **0.1.1-experiment**。test2是包含日志核验、MIT和干净包检查的快照标识，不是应用版本升级。不要使用旧v0.1.1-experiment标签或滚动main代替。

下载：https://github.com/DDHKai/dagongren-qiuzhi/archive/refs/tags/v0.1.1-test2.zip

这是6家合成数据演示，不测试真实简历、BOSS登录、AI或投递。不输入个人资料。Windows与macOS各自执行一次；没有对应系统就写未测试，不模拟冒充。

## 1 下载与环境

保存ZIP并解压到全新目录，建议路径带空格，例如Windows的D盘测试目录。不要覆盖旧版本、不复制旧venv、不改代码。确认VERSION显示0.1.1-experiment，存在scripts/audit_test_log.py及本文件。

需要已有Python 3.10+。Windows先运行`py -3 --version`或`python --version`；macOS运行`python3 --version`。没有Python时记录前置条件缺失，不能报告完整部署通过；不自行复制工具内置venv。安装或选择独立解释器时注明其来源，勿宣称未核验的D盘独立性。下面Windows命令假设python可用，实际若仅py可用，将python替换成py -3；不要修改脚本。

## 2 基础检查

在项目根目录新建test-results目录，保存以下命令的标准输出和错误输出。Windows PowerShell：

```powershell
New-Item -ItemType Directory -Force test-results | Out-Null
python --version > test-results/python-version.txt 2>&1
python scripts/verify_release.py > test-results/checks.txt 2>&1
$LASTEXITCODE | Out-File test-results/checks-exit.txt
python scripts/check_release_layout.py --clean > test-results/clean-check.txt 2>&1
$LASTEXITCODE | Out-File test-results/clean-exit.txt
```

macOS Terminal：

```sh
mkdir -p test-results
python3 --version > test-results/python-version.txt 2>&1
python3 scripts/verify_release.py > test-results/checks.txt 2>&1
echo $? > test-results/checks-exit.txt
python3 scripts/check_release_layout.py --clean > test-results/clean-check.txt 2>&1
echo $? > test-results/clean-exit.txt
```

Node是可选项，缺少时JS测试应显示SKIP而非伪装通过。保留原始检查输出，失败不删改、不修代码后再冒充原版本通过。

## 3 启动与停止

Windows双击start-windows.bat；macOS在项目根目录运行`sh ./start-macos.command`。浏览器没有自动打开时手动复制终端地址。保存启动终端截图（隐藏个人路径）。不用管理员权限，不开放公网端口。停止用Ctrl+C。

## 4 浏览器操作（按顺序）

T01 默认18K、双休必须、职责交集：三组ID应分别为[S01,S06]、[S02]、[S03,S04,S05]。

T02 双休改不在意，应用：S04进第一组，S02仍待核实。

T03 薪资改20，应用：S06进取舍组。

T04 切换披露待遇并应用：确认组内固定月薪下限优先，不跨组；截图实际顺序。

T05 对S01选择再取消：计数1再0。

T06 前先将条件明确恢复为18K、双休必须、职责交集并应用，记录这一额外事件。此时取舍组应为[S03,S04,S05]，再置顶S04：只移至本组第一，全局第一仍是S01。不能直接沿用T04后的条件；此前版本该步骤的前置条件有误。

T07 隐藏S06，随后重置：隐藏计数1再0，卡片恢复；选择/置顶清空，已应用条件保留。

T08 分别输入空值、-1、201并应用：均拒绝，已应用条件不改变。恢复18并应用。

T09 导出测试日志，确认JSON真实保存，放入test-results并改名为Windows-test-log.json或macOS-test-log.json。记录下载失败或浏览器阻止，不把请求导出等同文件保存成功。

T10 保持第一个启动器运行，再启动一个：应自动换端口。两页能访问，最后两个进程分别Ctrl+C停止。记录两端口及停止后刷新不能继续访问（不要仅凭已打开页面判断服务仍在）。

每项写预期/实际/PASS或FAIL；自动化需附测试脚本及断言输出，说明无头/有头，不称等价人工体验。人工体验另行记录。失败先截图及导出，不刷新丢失现场。

## 5 核验日志

Windows示例（macOS将python换成python3并替换日志名）：

```powershell
python scripts/audit_test_log.py test-results/Windows-test-log.json --output test-results/audit-report.json
```

退出码0是内部一致性通过，1异常，2证据不足。不是全部用例通过认证。执行失败也保留输出/截图。

## 6 回传内容

仅压缩test-results及必要的脱敏截图、自动化脚本；命名Windows-test2-results.zip或macOS-test2-results.zip。不要压缩整个项目、运行时、数据库、Cookie或真实简历。

目录应包含：python-version.txt、checks.txt、checks-exit.txt、clean-check.txt、clean-exit.txt、对应系统-test-log.json、audit-report.json、测试说明.txt及必要截图。文件无法生成时说明缺失原因，不伪造文件。

测试说明.txt填写：下载URL和标签v0.1.1-test2、应用版本、系统版本/芯片架构、浏览器版本、Python来源、T01–T10逐项实际结果、启动/停止结果、未测项目、人工或自动化方式、异常步骤及复现。可记录ZIP的SHA256用于区分下载物，但不能与本地自制ZIP校验值混用。

人工审阅所有回传文本及截图，遮住用户名、私人路径、账号和局域网信息；不要公开Issue上传原始诊断。将结果包发回开发对话。测试结束停止两个服务。
