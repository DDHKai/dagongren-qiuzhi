# 打工人 · 求职决策助手

当前实验版：0.2.0-experiment（版本入口VERSION）。

历史桌面合成发布：[v0.1.1-desktop-experiment](https://github.com/DDHKai/dagongren-qiuzhi/releases/tag/v0.1.1-desktop-experiment)。旧版范围见[发布范围、安装与限制](docs/desktop-release.md)。

当前跨设备测试快照为 **v0.2.0-mvp-test1**（应用版本0.2.0-experiment）；请按[本轮Windows／macOS下载、部署、测试与回传指令](docs/device-mvp-run.md)执行。使用新Release附件，不与旧v0.1.1-test2或滚动main混用。

帮助有工作经验的求职者，将经历、岗位需求和公司证据放在一起，做有依据的选择。

**历史合成发布0.1.1-experiment：下述旧实验范围不代表新MVP能力。** 可运行的是合成岗位交互页和独立证据模块；不登录BOSS、不调用模型、不采集真实岗位、不投递。已收到Windows与Intel macOS的无头Chrome实机回传，具体环境与未测项见[验收记录](docs/test2-validation.md)。

## 当前能力

当前MVP动作范围收敛为[账号确认后的授权收藏](docs/favorite-mvp.md)：选定岗位、绑定当前Chrome账号、逐项刷新核对、最多一次收藏点击、页面刷新后验证及防重复。简历投递和沟通由用户在平台完成，自动发送只保留关闭的升级口。已按用户明确指定的单岗位完成真实试跑：首轮状态文案漏识别后只读补证，保留未决历史并修复回归；没有重复点击。具体范围和限制见收藏MVP，不把单例当作所有页面验证。

main新增[动作限定授权与人工接管台账](docs/actions.md)：具体岗位／动作、只读刷新、版本与时效保护、跨记录防重复、前后观察与报告标记。自动收藏／自动沟通仍未接入，所有平台动作由本人执行，消息不标作已发送。

main新增[本轮结果汇总与私人导出](docs/result-report.md)：公司规模、硬条件、能力复核和公司研究分开展示；人工选择10＋10目标、个人顺序、三项沟通提纲及HTML／JSON导出。证据变化旧报告失效，不凑数、不自动投递。

main新增[公司财报固定信源留证](docs/company-research.md)：工作区第8节支持指定官方PDF/HTML下载、原文hash、指标引用及人工风险复核。尚未自动定位最新报告或判断成长，未知不作为淘汰理由；不生成总分。

main新增[能力证据对照与人工复核](docs/ability-review.md)：岗位片段检索候选事实、人工说明任务交集与缺口、保存引用及方向意愿。默认无正向结论，不生成总分，证据变化旧稿失效。它不是自动AI语义判断，真实岗位草稿仍需人工复核。

main新增[真实岗位条件预筛](docs/prescreen.md)：可在本地工作区导入采集检查点，明确选择固定底薪/发布区间等口径，展示符合、未知、冲突及原文引用。仅限所配置条件，不是AI能力匹配，不等于最终推荐，真实报告保存在本机。

main现有[本地真实简历工作区](docs/private-workspace.md)：`start-windows.bat --workspace`或`sh ./start-macos.command --workspace`。支持文件导入、页/段审阅、字段原文映射、条件保存与逐项事实确认，数据落在本机私有目录。已可导入真实岗位检查点并开展人工辅助对照，尚未接入模型；macOS新工作区仍待验证。下表主要描述既有合成实验发布，不把main新能力冒称已进入旧Release。

main新增[PDF/DOCX原文提取与人工字段校对](docs/resume-document.md)：PDF可选pypdf依赖，保留页/段引用、显式映射及不可覆盖的校对版本；不含OCR或自动履历识别，已接入本地工作区。

main新增真实输入基础模块：`scripts/resume_workspace.py`可本地导入UTF-8文本/结构化JSON并保存待确认事实及条件；该独立模块本身不解析PDF/DOCX，文档与网页由上方模块接续；不含自动语义判断。它不属于此前固定实验Release。真实求职版的10阶段范围、命令与当前进度见[路线图](docs/real-job-roadmap.md)，不沿用合成发布的100%。

| 能力 | 实际状态 |
| --- | --- |
| 条件分组、偏好排序、选择/隐藏、组内置顶 | 已实现；6家虚构公司 |
| schema 2交互日志 | 已实现；人工导出合成状态 |
| SQLite存储、去重、轮次、事实引用及证据ID | 独立模块；未接成完整网页后端，引用存在不证明判断正确 |
| 双系统启动及端口重试 | test2双系统自动化回传通过；人工有头体验仍未验证 |
| 真实简历导入、AI匹配、岗位/财报采集、沟通投递 | 当前发布版不支持 |

## 本轮MVP测试版

下载[v0.2.0-mvp-test1 Release附件](https://github.com/DDHKai/dagongren-qiuzhi/releases/tag/v0.2.0-mvp-test1)，按[完整测试指令](docs/device-mvp-run.md)校验、解压到全新目录。真实工作区使用`start-windows.bat --workspace`或`sh ./start-macos.command --workspace`。需要Python 3.10+、Node 22+和已安装Chrome；PDF另需可选依赖。不提供模型自动语义评审，不默认授权真实收藏。

## 历史合成演示

[下载旧合成测试快照ZIP](https://github.com/DDHKai/dagongren-qiuzhi/archive/refs/tags/v0.1.1-test2.zip)，解压到新目录。无需模型Key或BOSS账号，不输入个人资料。test2标签不随main更新；T06前置条件修订见main中的测试指令。

- 浏览器打开 `web/index.html`，不覆盖启动器测试。
- 已装Python 3.10+：Windows双击 `start-windows.bat`。
- macOS在解压目录执行 `sh ./start-macos.command`，需要已有Python 3.10+。
- 仅监听本机，打印实际端口，Ctrl+C停止。不捆绑Python，不宣称venv独立于原安装位置。

完整步骤和T01–T10见[桌面测试](docs/desktop-testing.md)。没有签名安装包、自动更新或云服务。旧标签不自动包含main新增文档。

## 设计方向（未完整实现）

经历梳理 → 条件确认 → 市场搜索 → 岗位与公司研究 → 用户选择 → 授权操作与反馈。

默认100家不同公司、目标10优选+10候选，不足不凑数。条件分必须、偏好、不在意。岗位能力、待遇、公司经营分开，不设总匹配分；未知不记负面、人数不是越大越好。推荐解释真实经历交集、核实问题和差距，保留自主排序。

公司研究区分行业、公司和岗位，关注现金回收、短债、持续经营，不以股价代替经营。财报计划主源：A股[巨潮](https://www.cninfo.com.cn/new/index)、港股[披露易](https://www.hkexnews.hk/index_c.htm)、美股[SEC EDGAR](https://www.sec.gov/search-filings)，当前没有自动适配器。未来外部动作须具体授权、刷新和结果证据，点击不等于成功。

## 测试与输出

版本及文档标记检查：`python scripts/check_release_layout.py`。仅用公开包在新建带空格目录解压、校验清单并回归：`python scripts/check_release_layout.py --clean`。该演练使用本机已有解释器，不替代新机器或macOS实测。每次变更包内容需重新生成SHA256，不能只按版本名认定包相同。

Python 3.10+标准库，不需要第三方Python依赖：

```text
python scripts/test_project_store.py
python scripts/test_review_store.py
python scripts/test_candidate_facts.py
python scripts/test_desktop_launcher.py
python scripts/check_public_files.py
python scripts/package_experiment.py
```

可选Node 18+：`node scripts/test_experiment.mjs`，DOM桩检查不替代浏览器。打包白名单文件，输出ZIP、清单与SHA256至dist；自制ZIP与GitHub源码ZIP不应混用校验值。

导出dagongren-test-log.json，附系统/浏览器及失败步骤人工回传。日志内存保存、刷新清空；下载请求不代表实际保存。日志不证明全部断言通过或人类决策时间改善。

## 隐私与安全

收到schema 2测试日志后，可运行 `python scripts/audit_test_log.py Windows-test-log.json --output audit-report.json`，自动检查合成分组、排序、事件和计数，输出通过/异常/证据不足。仅认证内部一致性，不代表T01–T10全覆盖或实机验证通过。详见[日志核验说明](docs/log-audit.md)。统一自检入口：`python scripts/verify_release.py`。

演示页无模型调用、遥测或自动上传。Python模块可写本地数据库，不能宣称整个项目不落盘。真实简历、报告、会话、凭据、数据库及事实盐不公开；去姓名不等于匿名。逐文件白名单与扫描辅助人工审核，不保证绝对匿名。未来外部模型前须说明服务与必要字段并确认。见[证据边界](docs/开源边界与事实证据.md)、[安全反馈](SECURITY.md)。

## 参考、引用与许可

文档及产品研究参考[求职舱](https://github.com/kyle-kw/ai-job-app)、[自动投递项目](https://github.com/bazxhy/Automated-Resume-Submission)、[采集工具](https://github.com/eatmoreduck/boss-zhipin-scraper)。本次文本独立撰写，当前公开实现未引入三库代码/资源；参考不是依赖，不暗示作者合作或背书。未来复用须逐文件核对许可、版权和修改记录。详见[结构拆解](docs/reference-structure.md)。

原创公开内容按[MIT许可证](LICENSE)提供；第三方内容不因此重新授权。

## 使用边界与免责声明

实验信息不保证岗位有效、待遇兑现、匹配准确、经营安全或面试录用。招聘披露不是个人报价，集团财报不是实际雇主独立财务。重要判断应核实原始资料，必要时寻求专业意见。

本项目不是BOSS、交易所或监管机构官方产品，未获其背书。未来平台访问须遵守适用规则、授权和平台协议，不使用他人会话、不绕过验证、不制造不合理访问负担。免责声明不替代应承担的义务，也不免除适用法律下不可免除的责任；按现状条款见MIT原文。

## 反馈与贡献

请提供版本、最小复现、预期/实际及合成日志，不在公开Issue发送个人履历、Cookie、令牌或私人路径。[贡献说明](CONTRIBUTING.md)列明审查和第三方归属要求。
