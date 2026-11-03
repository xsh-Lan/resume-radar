# 简历雷达

当前版本：**0.16**。从岗位发现、简历诊断、能力差距分析到简历优化的求职工作流 Agent。在 Codex 对话中一次确定方向、JD来源与目标岗位，由 Codex 直接执行，在本机网页中将 PDF 原件与诊断、改写及固定经历案例对照。支持多职业分析；随包案例覆盖产品经理细分岗位。

## 安装与使用

解压发布包，将其中的 resume-radar 文件夹放入 ~/.codex/skills/（Windows 通常为 C:/Users/你的用户名/.codex/skills/）。重新打开 Codex 聊天后使用 `$resume-radar`，提供能选中文字的 PDF，可同时提供意向方向或 JD。

需要 Python 3.10+ 和 PyMuPDF。Codex 根据 skill 说明检查依赖，缺少时运行 `python -m pip install -r <安装目录>/requirements.txt`。浏览器展示不需要 Chrome 扩展、模型 Key 或网页后台。首版不处理 Word 自动转换和扫描件。

用户只需一次选择“本次求职目标”，同时确定方向、JD来源与具体岗位。第一项为“不明确，帮我推荐”，授权Agent检索并推荐主目标。默认全文诊断、逐句审阅与优化全文，不再询问输出范围或追问事实；分析后打开原件对照报告。保留四个核心 skill 的方法与内容。完整评估通过校验后打开本机报告：中间展示原始 PDF 各页，右侧给出对应诊断和案例，支持点击编号双向定位、缩放、筛选、复制及本机处理标记。修改建议不改写 PDF。

六个入口为整体判断、模块诊断、逐句审阅、待补充事项、岗位要求及经历示例库。Hired 固定库含 41 类产品经理岗位、351 个细分方向、2,125 组案例，保留原文与教学说明；不声称案例是真实已核验履历，不用案例替代候选人事实。非产品经理目标不强配案例。不使用 AI 生成新案例补库。

## 开发与打包

四个核心 skill 位于 skills/：resume-radar、job-application-assistant、resume-refiner、interview-prep。固定库在 assets/hired-library/，原独立教学卡片模块已移除。

```text
python scripts/workflow.py init --resume <原件.pdf> --run-dir <新运行目录> --candidate-key <候选人键> --guided
python scripts/example_library.py --query <具体职责词>
python scripts/workflow.py validate --run-dir <运行目录>
python scripts/render_report.py <运行目录> --output-dir <运行目录>/report --open
python scripts/package_skill.py --output <发布目录>/resume-radar-0.16.zip
```

初始化只保存原件、提取来源和空分析文件，不自动完成分析。完整任务只需一次合并目标选择，具体步骤见 skills/resume-radar/references/guided-workflow.md。Codex 依照数据契约实际完成判断、改写和复核，再渲染报告。PDF 对照操作见 skills/resume-radar/references/workbench.md。

运行资料保存到独立候选人与版本目录，不放进 skill。报告文件夹含 HTML、案例脚本、页面图片和原 PDF；移动时保留整个文件夹。打包脚本按白名单收集程序与固定资源，不包含候选人信息、测试输出或源码仓库。处理标记只保存在当前浏览器，补充事实仍需回到 Codex 更新。

运行 `python evals/run_eval.py` 验证数据与 PDF 定位行为。更新见 CHANGELOG.md，来源说明见 THIRD_PARTY_NOTICES.md。

## 三路由与确认

Route 01：已有 JD 精准匹配；Route 02：确认方向后自动检索真实岗位，由用户选定 JD；Route 03：不使用 JD 的通用诊断。目标岗位首先提供“不明确”选项，再提供“已有意向岗位”。方向、JD来源与岗位合并为同一次选择，用户确认或委托后直接执行，不再增加分析方案与事实补充关卡。
