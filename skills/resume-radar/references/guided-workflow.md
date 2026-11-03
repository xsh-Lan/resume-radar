# 在 Codex 中连续完成求职工作流

需求确认、岗位选择、分析方案确认和事实追问都在当前 Codex 对话完成。收到用户回答后继续下一步，分析与校验完成后才打开原件对照报告。局部任务按已授权范围处理。已有运行与确认记录时接着执行，不重复询问。

ROOT 是含 scripts、standards、skills 的安装根目录；命令用绝对路径，个人资料放在用户工作区。

## Stage 1：对话确认需求

提取简历和已有指令/JD，用 workflow.py init --resume <PDF> --run-dir <新目录> --candidate-key <键> --guided 初始化；有 JD 加 --jd <JD.txt>。初始化只建立来源。

概括已知目标，只问缺失或改变路径的内容。优先使用宿主用户提问工具；没有时在当前对话提问并等待回答。可以一轮问目标与 JD 来源：

- 目标岗位：第一项“不明确，先帮我探索方向”，第二项“已有意向岗位”（填写岗位）。已有明确意向直接沿用。
- JD 来源：用户提供 / 自动寻找 / 通用诊断不使用 JD。
- 分析重点：岗位匹配、项目经历、业务价值、能力差距、表达结构。根据用户需求提出建议并允许修改，不逐字段盘问。

回答到达后，将实际用户回答保存为 stage1-reply.txt，将结构化结果写 goal-values.json：target_choice（unclear/specified）、target（不明确时为空）、jd_source（provided/auto/none）、focus（非空列表）。goal-prefill.json 保存此前建议，可为空对象。已有明确指令可作为回答来源；预填、默认和沉默均不算用户确认。

```text
python <ROOT>/scripts/confirm.py --run-dir <目录> --stage 1 --prefill <目录>/goal-prefill.json --record <目录>/goal-values.json --response <目录>/stage1-reply.txt
```

## 准备岗位和方案

目标是否明确与 JD 来源分别处理。Route 01（provided）核对用户完整 JD；Route 02（auto）从简历证据推荐少量方向，用宿主浏览工具读取真实 JD，按 job-discovery.md 用 add-jd 导入；Route 03（none）准备经历结构、项目价值、个人贡献、结果证据及表达诊断，不自动找岗位。

Route 02 在当前对话呈现少量候选岗位、公司、来源链接、推荐理由与招聘状态，让用户选择；必要时先问城市、职级等会影响结果的约束。检索失败时在当前对话说明并选择提供 JD、换方向或通用诊断，保留已答内容。

写 plan-prefill.json：stage1_hash（confirmation.json 当前值）、jobs（source_id、title、company、url、availability、rationale）、selected_jd_ids、capabilities、modification_scope、sentence_review、optimized_resume。通用诊断 jobs 与 selected_jd_ids 为空，capabilities 写通用诊断维度。只把用户选定的实际 JD 纳入分析，不代选检索的第一个候选。

## Stage 2：对话确认方案

简要呈现目标/JD、核心能力要求、修改章节、是否逐句审阅、是否生成优化全文，用一轮明确回答确认执行。已有明确选项直接沿用，只问剩余决策。可使用“按此方案开始”“调整方案”选项。

实际回答保存为 stage2-reply.txt，确认选项写 plan-values.json：target、selected_jd_ids、capabilities、modification_scope、sentence_review、optimized_resume。两个开关为布尔值，修改范围具体到章节或全文。

```text
python <ROOT>/scripts/confirm.py --run-dir <目录> --stage 2 --prefill <目录>/plan-prefill.json --record <目录>/plan-values.json --response <目录>/stage2-reply.txt
python <ROOT>/scripts/confirm.py --run-dir <目录> --ready
```

收到回答后检查并执行，不再要求用户通知“已提交，请继续”。旧网页保存的选择继续有效；新任务默认对话确认，旧网页仅在显式请求时使用兼容入口。

## 执行、恢复与交付

ready 通过后正式分析：run.mode 使用 01→jd、02→direction、03→general，target 使用 Stage 2 已确认目标。新 workflow_version=0.15，旧 0.14 兼容。需求或来源变化时只在当前对话重新确认受影响选项。

按方案调用专业模块，必要事实追问留在 Codex。sentence_review=false 按经历段落组织并保持内部来源覆盖；optimized_resume=false 时 final_text 留空，true 时生成忠实优化全文。通用诊断允许 requirements 为空，market_search=not_needed，不伪造招聘判断。

完成聚焦复核、来源与方案校验后，使用 render_report.py --open 打开原件对照报告。网页用于阅读、定位、案例和本机处理标记，当前流程不设置网页确认关卡。用户后续修改需求仍在当前 Codex 对话提出。
