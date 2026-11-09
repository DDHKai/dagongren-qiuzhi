# 求职决策助手（原型）

将简历事实、岗位要求及公司公开资料分开保存，支持有依据的求职判断。当前是本地原型，不是完整自动求职产品。

## 开源与隐私

仅发布经过审核的通用模块和合成样例。真实简历、个人报告、登录状态、来源原文、数据库和本机配置不提交。姓名替换并不意味着履历已匿名，组合经历和业绩也可能识别个人。

当前`.gitignore`按允许清单开放少量代码；旧试跑脚本仍留本地且默认排除，迁移为通用模块后才逐项纳入。发布前运行`python scripts/check_public_files.py`，检查暂存文件清单并人工复核；忽略规则不会移除已经跟踪或历史提交的数据。本目录已使用 Git 管理版本，公开仓库为 https://github.com/DDHKai/dagongren-qiuzhi 。仅同步上述白名单文件，真实数据继续保留本地。许可证在正式发布前选定。

## 已有通用模块

- `scripts/project_store.py`：SQLite来源存储、去重与轮次阶段。
- `scripts/review_store.py`：事实、推断和未知的引用校验。
- `scripts/candidate_facts.py`：本地稳定证据ID与草稿关联。
- `examples/synthetic-resume.json`：完全合成的最小样例。

需要Python3.10+，上述模块使用标准库。测试：

```text
python scripts/test_project_store.py
python scripts/test_review_store.py
python scripts/test_candidate_facts.py
python scripts/check_public_files.py
```

候选事实ID使用本地随机盐，引用校验只证明文字存在，不代表判断正确。迁移命令仍面向本机试跑目录，完整跨用户入口、自动采集与发布打包尚待实现。
