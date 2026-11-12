# 可转发：Windows／macOS 收藏MVP测试与回传

请测试仓库 **DDHKai/dagongren-qiuzhi** 的固定快照 **v0.2.0-mvp-test1**，应用版本 **0.2.0-experiment**。这是预发布验收，不是正式上线证明。Windows和macOS分别用真实设备执行；无对应系统就写未测试，不模拟冒充。iPhone/iOS不在本轮范围。不要用旧test2或滚动main。

## 一、下载正确版本

打开[本轮Release](https://github.com/DDHKai/dagongren-qiuzhi/releases/tag/v0.2.0-mvp-test1)，下载两个附件：

- `dagongren-0.2.0-experiment.zip`
- `dagongren-0.2.0-experiment.zip.sha256`

直接下载：[ZIP](https://github.com/DDHKai/dagongren-qiuzhi/releases/download/v0.2.0-mvp-test1/dagongren-0.2.0-experiment.zip)、[SHA256](https://github.com/DDHKai/dagongren-qiuzhi/releases/download/v0.2.0-mvp-test1/dagongren-0.2.0-experiment.zip.sha256)。**不要点GitHub自动生成的“Source code (zip)”**：本轮附件另有MANIFEST，测试工具会核对源码、清单和ZIP三者一致。

Windows下载、源码、结果和新建虚拟环境放D盘或E盘，不下载到C盘。建议全新带空格目录，如`D:\MVP Test1\`；macOS也使用全新带空格目录。不要覆盖旧部署、不复制旧venv或浏览器配置。解压后进入`dagongren-experiment`目录，应该同时看到VERSION、TEST_SNAPSHOT、MANIFEST.json和scripts。

确认VERSION为0.2.0-experiment、TEST_SNAPSHOT为v0.2.0-mvp-test1。保留原始ZIP和校验文件，测试时传给脚本，不重新压一个包冒充下载物。

## 二、环境要求与边界

需要Python **3.10+**、Node **22+**、已安装的Google Chrome。无需npm依赖、无需Playwright、无需再下载浏览器。macOS请记录Intel/x86_64还是Apple Silicon/arm64，不替代另一架构结论。

Python请记录真实来源和版本。已有官方独立解释器优先；没有运行时则记录前置条件缺失，不能用工具内置解释器冒称普通部署通过。工具托管解释器可以用于定位问题，但必须如实标明，另列独立运行时验收缺口。Windows源码在D盘不等于解释器和标准库在D盘；工具会分别记录executable/prefix/basePrefix/stdlib的盘符。

官方embeddable Python默认隔离sys.path，可能出现ModuleNotFoundError。保留首次失败，不改项目源码绕过；如果另行调整了运行时配置或换了正常安装版，要写明改了什么并在新结果目录重跑，不删除第一轮。不要复制工具的venv或宣称未验证的可移植性。

PDF为可选功能，使用pypdf依赖。若要验证PDF，在本机项目虚拟环境安装`requirements-resume.txt`；缺依赖时记录PDF未测，不能把DOCX/TXT通过算作PDF通过。合成核心测试本身不要求输入真实简历。

## 三、先跑A：自动合成检查（不登录BOSS、不真实收藏）

以下命令均在解压后的项目根目录执行。按实际解释器位置修改变量，路径保留引号。结果目录必须全新，重复测试用test-results-2等，不覆盖失败现场。

Windows PowerShell示例：

```powershell
$TestPython = "D:\你的Python目录\python.exe"
& $TestPython --version
node --version
& $TestPython scripts/run_device_checks.py --archive "D:\MVP Test1\dagongren-0.2.0-experiment.zip" --chrome "C:\Program Files\Google\Chrome\Application\chrome.exe" --python-source "按实际填写，例如python.org独立安装" --output "test-results"
$LASTEXITCODE
```

若只有`py -3`，可以将`& $TestPython`换成`py -3`；实际解释器位置仍须在输出中核对。Chrome也可能装在Program Files (x86)或其他位置，按实际填写，不复制浏览器到项目。

macOS Terminal示例：

```sh
TEST_PYTHON="$(command -v python3)"
"$TEST_PYTHON" --version
node --version
"$TEST_PYTHON" scripts/run_device_checks.py --archive "/实际下载目录/dagongren-0.2.0-experiment.zip" --chrome "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --python-source "按实际填写解释器来源" --output "test-results"
echo $?
```

工具自动执行：来源/清单/校验核对 → 全套Python和JS回归 → 带空格目录重新解压演练 → 真实无头Chrome操作本地工作区、下载JSON/HTML并离线打开。**收藏worker是合成替身**，另有合成CDP子进程测试；它们不接触真实BOSS，不证明真实收藏、人工体验或市场筛选效果。

退出码0仅表示合成核心通过；1表示检查失败，2表示来源或前置条件不完整。仍须看device-summary.json、未测项和手工体验。缺Node或Chrome不能把SKIP算完整通过。RAW-PRIVATE保留原始输出，只留本机；可分享的文本已遮挡项目及主目录路径，但仍须人工检查。

## 四、再跑B：人工有头工作区体验（只用合成资料）

Windows：`start-windows.bat --workspace --data data/manual-device-check`。

macOS：`sh ./start-macos.command --workspace --data data/manual-device-check`。

必要时先设置`DAGONGREN_PYTHON`为上述解释器路径。端口默认8765，被占用时自动顺延。确认页面是“真实简历本地工作区”；不带--workspace打开的旧6卡片演示不能代替本轮MVP。

按顺序填写test-results/manual-results.md：

1. **M01启动**：记录显示地址、版本、是否有报错。只监听127.0.0.1，不开放公网。
2. **M02简历**：导入examples/synthetic-resume.json；条件可填必须双休、18K、杭州。只确认两条合成任务：“负责示例业务的数据复盘。”和“使用自动化工具整理示例报表。”，不把合成业绩当本人真实经历。
3. **M03预筛**：第6节导入examples/synthetic-market.json，明确设杭州、固定底薪18K、必须双休、本人学历大专并确认。预期3岗位/2公司：符合1、值得核实1、存在取舍1；公司人数20—99与100—499清楚。仅有区间的岗位固定底薪仍未知。
4. **M04能力**：第7节选择“电商数据运营”，生成草稿；将“负责示例业务的数据复盘。”对应至已确认同一句任务，选直接证据并写合成复核理由，保存。不能把AI标题当Python/RAG能力证明。
5. **M05公司**：第8节选择虚构甲公司，保留未上市／身份待核实并保存，不下载虚构链接，不据此排除岗位。
6. **M06汇总**：第9节生成，显示2/100而非跑满100；优选0、候选0。将电商数据运营明确选为优选并写理由，变为优选1。不能自动补20家，也不能把未复核岗位直接纳入优选。
7. **M07选择**：个人重排一个岗位并保存；对虚构乙公司写“大小休与双休要求不符”并选本轮不考虑。查看条件差异和单项取舍假设，原18K/双休条件应保持。系统顺序与本人顺序分别记录。
8. **M08导出**：确认私人导出提示，实际下载HTML和JSON并打开。这里只含合成资料，可以附回传；不要用真实简历报告代替。下载请求不等于文件落盘。
9. **M09过期**：第7节重新生成能力草稿，旧汇总应标过期并禁用导出；重新生成汇总后不自动继承旧选择。截图真实状态。
10. **M10重启/端口**：停止后重启同一数据目录，记录应保留。端口冲突测试用第二个新数据目录`data/manual-device-check-2`，不要两个实例同时写同一个目录。记录实际两个端口；两个服务都Ctrl+C停止，刷新/新请求应不能访问，不能凭缓存页认定运行中。
11. **M11可选解析**：用自己制作的纯合成DOCX/PDF检验原文页段和校对。扫描件、乱码、缺依赖、加密或空白PDF应如实记录，不改扩展名冒充成功。

不要点击虚构岗位链接去线上测试，不在合成岗位上绑定真实账号或尝试收藏。自动脚本已用隔离夹具覆盖授权收藏逻辑；B单独记录真人体验。

## 五、C：真实BOSS与收藏（仅设备主人明确同意时）

默认**未测试**，不为完成测试自行找岗位收藏。没有设备主人在场、没有具体岗位授权时就写未测，继续完成A/B。

主人同意后，用项目专用Chrome配置，由本人登录；不发验证码、密码或Cookie给任何人。启动命令示例：

```text
python scripts/start_collector_chrome.py --chrome "实际Chrome可执行文件路径" --profile data/chrome-device-check --port 9333
```

macOS的Chrome可执行文件是`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`。此步骤会打开独立窗口供本人登录；其他采集/收藏操作通过该测试窗口进行，不占鼠标键盘。不能复制日常Chrome配置，CDP仅本机。

使用examples/collector-config.json为参考，在data下新建真实任务配置并明确关键词/城市/限额；不会自动扩充100家。先小批核对岗位与公司来源，再按[收藏MVP](favorite-mvp.md)完成真实输入/评审/选择、只读账号核对、明确岗位收藏授权及执行。必须保存前后证据，已收藏不重复点击，“取消感兴趣＋active”表示保存状态；不点击取消或立即沟通。未知结果只用只读核对按钮，不重复执行。

不要把之前开发设备的测试岗位或本指南当作新账号的收藏授权。主人需明确具体岗位。即使测试人员是AI，也不能根据“测试部署”擅自扩大成批量真实收藏。沟通、简历、附件、回复均不在测试范围，由主人自行操作。

真实输入、BOSS观察、绑定、盐、Chrome配置、SQLite和worker请求**都留本机**。回传只写匿名结果：是否取得账号标记、操作前已有收藏/新收藏/停止/未知、是否重载确认、是否无沟通/投递、异常代码；不附手机号、公司岗位链接或截图中的头像。

## 六、D：真实100家公司质量验收（后续独立任务）

部署和合成通过不等于推荐有效。主人准备好本人材料后，另起明确任务：100个不同平台公司标识覆盖、相关岗位优先、多岗位去重、10优选＋10候选目标不凑数、硬条件/未知/排除共性、人工复核及漏选检查、实际决策耗时。采集器可能受首屏、关键词或平台验证限制，覆盖不足必须原样反馈，不悄悄放宽条件。没有完成就写未测，本轮不得以A/B替代D，也不在本指南默认要求批量收藏20家。

## 七、回传什么、如何打包

填写manual-results.md，人工看一遍所有文本与截图：遮住用户名、私人路径、主机名、真实账号、真实履历及求职选择。不要公开发Issue。仅发回开发对话。

Windows：

```powershell
& $TestPython scripts/package_device_feedback.py --results test-results --output "Windows-mvp-test1-results.zip" --reviewed
```

macOS：

```sh
"$TEST_PYTHON" scripts/package_device_feedback.py --results test-results --output "macOS-mvp-test1-results.zip" --reviewed
```

请回传对应系统ZIP及其.zip.sha256。打包器只选诊断、合成报告、已审阅PNG和人工说明，包含文件hash及缺失清单，不上传；排除RAW-PRIVATE和所有工作区/Chrome数据。正则检查不是完整匿名保证，`--reviewed`表示你确实人工核对过。

最终包通常包含：device-summary.json、source-check.json、environment.json、steps.json、checks/clean-check/browser-check.txt、browser-summary.json、synthetic-result.json/html、manual-results.md、screenshots/和feedback-manifest.json。失败或未执行时允许缺文件，必须说明原因，不能伪造。重试用新目录并保留/回传两次结果，写明环境变更；不改项目代码再声称原快照通过。

请在反馈首句写：**系统／架构、A自动检查是否通过、B人工体验是否完成、C真实收藏是否测、D百家公司是否测**。这四项分别判断，不合成一个“全部通过”。测试结束停掉服务及本次专用Chrome。

## 本地预检记录与判定边界

2026-11-12已在开发设备从新ZIP解压至带空格目录，完整演练来源校验、基础回归、二次干净目录检查、无头Chrome合成流程和反馈打包，并核对合成市场手工指令所用的3岗位/2公司、三组各1、单项周末取舍新增1家公司及过期保护。返回文本和截图已检查为合成资料；原始stdout/stderr按字节单独留在RAW-PRIVATE，共享副本规范为UTF-8换行，不改变退出码。

开发设备使用工具托管Python，已如实标记；这只证明工具链在当前环境跑通，不能作为其他Windows或macOS独立部署通过。正式结论仍分别等待目标设备A自动检查、B真人体验，以及主人选择执行的C/D反馈。预发布快照不宣称已经完成这些验收。
