# PDF与DOCX本地提取及校对

这是人工校对入口，不是自动识别完整履历或OCR。DOCX用标准库读取OOXML段落及表格内文字；PDF可选依赖pypdf 6.21.4，依赖文件requirements-resume.txt。请在用户选定的环境安装：`python -m pip install -r requirements-resume.txt`，项目不自动安装或联网发送资料，不自动下载模型。

## 提取

```text
python scripts/resume_document.py extract --source 自己的简历.pdf --output data/private-documents/review-001
```

也支持.docx，不支持旧.doc。输出原始source.pdf/source.docx、extraction.json（PDF逐页，DOCX逐段及部件位置）、review.html和mapping.json。新目录必须为空；所有产物私有，不上传公开Issue。HTML仅展示转义后的原文并链接本地原文件，无脚本或外部资源；附件里的文字不是可执行指令。

打开review.html，并同时打开原文件视觉核对。PDF可能乱序、乱码或已有OCR错误，DOCX浮动文字/图像/修订/复杂表格可能有遗漏；没有自动结构正确保证。不执行宏、链接、嵌入文件或PDF脚本。扫描件无文字时停在需OCR/人工转写状态，本阶段不自动补写。加密PDF拒绝，用户可提供自己有权访问的未加密副本。

## 人工字段映射

在mapping.json按原文unitId与精确quote填写字段，最后明确reviewerConfirmed=true。例（仅虚构字段）：

```json
{
  "reviewerConfirmed": true,
  "experiences": [{
    "company": [{"unitId":"u1","quote":"示例公司"}],
    "position": [{"unitId":"u2","quote":"示例岗位"}],
    "periodRaw": [{"unitId":"u3","quote":"2020—2022"}],
    "responsibilitiesRaw": [{"unitId":"u4","quote":"整理示例报表"}]
  }],
  "education": []
}
```

PDF使用p1/p2等页ID，DOCX使用u1/u2段落ID，以实际extraction.json为准。公司、职位、时间都是人工映射，不推断归属或换算年限。可选achievementsRaw；education可映射school、major、periodRaw、degreeRaw。每项必须为原文精确子串，不可把改写、猜测、外部指令塞入quote。不同来源矛盾应保留供复核，不合并成确定事实。

```text
python scripts/resume_document.py apply --folder data/private-documents/review-001 --mapping data/private-documents/review-001/mapping.json --output data/private-documents/review-001/resume-v001.json
python scripts/resume_workspace.py create --resume data/private-documents/review-001/resume-v001.json --conditions examples/synthetic-conditions.json --output data/private-intakes/review-001
```

真实使用须将合成条件换成自己的条件文件。每次修订生成新的resume-v002.json等文件，拒绝覆盖旧版本。原文件或提取稿hash变化会拒绝应用。输出sourceMap保留字段→原文片段→页/段定位。字段映射确认与事实ID逐条确认分开；都不等于第三方核实业绩。

## 限制及测试

限制10MB文件、100页、DOCX展开50MB、提取文字200万字符。不保证资源用量绝对受控，当前是本地受信任个人文档工具，尚未提供服务端上传隔离、OCR、自动多栏重建或恶意文档沙箱。CLI失败只显示通用提示，不打印个人正文。

`python scripts/test_resume_document.py`覆盖DOCX表格、映射及原文定位、虚构引用拒绝、篡改拒绝、显式复核、版本保护、XML声明拒绝；装有pypdf时追加空白及加密PDF测试，缺依赖显示SKIP而不是PDF已测。真实PDF视觉核对只保留本地记录，不提交真实附件或截图。

PDF提取参考pypdf官方说明：https://pypdf.readthedocs.io/en/6.21.4/user/extract-text.html 。pypdf为独立可选依赖，本地6.21.4元数据标注BSD-3-Clause，安装时保留依赖自带许可；MIT项目许可不重新授权该依赖，未将依赖代码打入本仓库或旧实验Release。
