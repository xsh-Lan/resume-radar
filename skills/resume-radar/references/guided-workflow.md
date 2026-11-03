# 求职工作流 Agent

完整任务使用三条路由与两阶段确认。局部润色、单独岗位分析、面试训练继续按已授权范围调用专业模块，不强制建立完整工作流。

ROOT 是同时含 scripts、standards、skills 的实际安装根目录。以下命令用绝对路径。首次依赖与 PDF 输入规则沿用 workbench.md。运行目录保存在用户工作区。

## Stage 1：需求确认

先提取、查看简历及用户已提供的指令/JD，只预判目标，不开始正式诊断。用 `workflow.py init --resume <PDF> --run-dir <新目录> --candidate-key <键> --guided` 初始化；有 JD 时加 `--jd <JD.txt>`。初始模式可暂定，正式分析前按确认路由更新。

在运行目录写 goal-prefill.json：target_choice（unclear/specified，网页第一项为“不明确，先帮我探索方向”）、target（AI 根据材料预填的岗位，可编辑）、jd_source（provided/auto/none）、focus（岗位匹配、项目经历、业务价值、能力差距、表达结构的子集）。已有 JD 默认 provided；用户明确要找岗位默认 auto；只有简历且无明确检索意图默认 none。网页仍由用户选择，不静默替用户确认。

```text
python <ROOT>/scripts/confirm.py --run-dir <目录> --stage 1 --prefill <目录>/goal-prefill.json --open
```

命令启动仅绑定 127.0.0.1 的临时页面，等待真实提交后退出。可用宿主后台进程运行；读取 confirmation.json 确认完成，不用修改该文件来绕过用户。未提交时等待用户，不开始依赖该决策的工作。

目标路由与 JD 来源独立：unclear 时不把 AI 推测当用户意向。若 JD 来源 auto，先从简历提出有依据的候选方向，再按方向检索候选 JD，在 Stage 2 让用户确认目标及选定 JD；若来源 none，则直接通用诊断并给可选方向建议，不擅自检索。specified 时以明确意向为主。

## 按 Stage 1 准备方案

- Route 01，provided：检查用户提供的完整 JD；缺少时请用户提供。只做要求初步拆解供方案确认。
- Route 02，auto：按已确认方向读取 job-discovery.md，用宿主浏览工具寻找并读取真实 JD，通过 workflow.py add-jd 保存原文及来源。网页展示候选的公司、职位、来源链接、推荐原因与招聘状态，由用户选择，不代选第一项。检索失败时说明并让用户改为提供 JD 或通用诊断，不能伪造候选。
- Route 03，none：不要求 JD，不联网检索岗位。准备经历结构、项目价值、个人贡献、业务证据和表达的通用分析方案。

写 plan-prefill.json：stage1_hash（从 confirmation.json 读取）、jobs（每项 source_id、title、company、url、availability、rationale）、selected_jd_ids（预选已有用户 JD；自动检索候选默认不选）、capabilities（基于选定范围的能力要求说明，可编辑）、modification_scope、sentence_review（布尔）、optimized_resume（布尔）。Route 03 的 jobs 与 selected_jd_ids 均为空，capabilities 写通用诊断维度，不冒充招聘要求。修改范围应明确章节或全文；不能只用“优化”代替具体范围。

## Stage 2：分析方案确认

```text
python <ROOT>/scripts/confirm.py --run-dir <目录> --stage 2 --prefill <目录>/plan-prefill.json --open
python <ROOT>/scripts/confirm.py --run-dir <目录> --ready
```

用户选择目标 JD、修改能力要求与范围，确定是否逐句审阅、是否生成优化简历。确认成功且 ready 校验通过后开始正式分析。需求变化须重新 Stage 1；旧方案自动失效。JD 原文变化须重新确认方案，不将旧同意套用到新材料。

## 执行与交付

读取 confirmation.json，将 run.mode 设为 01→jd、02→direction、03→general；target 使用 Stage 2 已确认目标；run.workflow_version 保持 0.14。Route 01 如从 auto 切换到 provided，须先用 workflow.py add-source --kind jd 导入用户 JD。Route 02 只围绕用户选择的 JD 建立要求，未选择的岗位不混入匹配结论；不作广泛市场统计断言。Route 03 可将 requirements 留空，market_search 使用 not_needed 并写通用诊断说明。

按确认范围调用岗位分析、简历编辑和事实追问模块。sentence_review=false 时按经历段落组织审阅，不输出逐句清单；内部仍保持来源覆盖。optimized_resume=false 时 final_text 留空；true 时生成忠实优化全文写入 final_text，未知事实放正文外，不承诺额外排版格式。

用既有校验器检查并生成 PDF 原件对照报告。校验器会检查新工作流已完成两阶段确认及 JD 来源是否变化。报告使用确认后的输出选项；通用诊断不伪造岗位匹配结论。固定库仅是表达参照，原件对应及案例机制沿用 workbench.md。
