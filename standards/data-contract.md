# 运行数据契约 v2.1

目录由 `workflow.py init` 新建。输入为完整提取并检查过的UTF8文本，保留姓名、电话、邮箱和链接，不自动脱敏；不改原文件。初始化生成以下六个JSON文件，空列表是待分析状态，不能直接交付。

## run.json

`schema_version`、`candidate_key`、`mode`由初始化确定。mode 为 jd/direction/explore。target_status 为 user_specified/user_selected/provisional/unresolved；暂定方向必须在 assumptions 披露依据与尚未确认内容。stage 是用户提供的职级或 unknown。

分析填入：summary（整体判断）、assumptions（字符串列表）、role_options（探索模式）、actions（行动）、final_text（请求全文改写时填写）、review（聚焦审阅）。分析与复核完成后将 status 改为 reviewed；追加来源后回到 draft，需再次复核。

role_options 每项：role、rationale、unknowns、evidence_ids。每个方向引用实际经历，选择服从用户目标；没有市场检索不声称在招、市场需求或录用概率。

actions 每项：type（edit/evidence/practice/decision）、text、diagnosis_ids。review 为 `{ "status": "completed", "findings": ["具体发现及关联ID；修正了什么或哪些仍未知"] }`。如无问题可为空列表；它记录本次内容审阅，不是外部证明。

正式报告建议填写 `report_overview`：headline（简短的核心判断，可用换行）、introduction（判断说明）、evidence_summary（已有经历依据）、gap_summary（关键证据缺口）、priorities（优先补充事项列表）。每项 priority 必须包含 title、text、diagnosis_ids，引用已存在的具体诊断。所有文案为已审阅结论的展示摘要，不新增事实、数据或岗位门槛。完整 summary 仍保存在“岗位方向与判断依据”内，避免为压缩首屏丢失限定条件。旧运行目录未填写此字段时，直接展示完整 summary 并使用既有行动，不自动推导新的能力判断。

## sources.json

`sources`包含来源对象：id、kind（resume/jd/jd_sample/followup/artifact）、text、sha256、units。脚本生成并保持不变。单元含 id、source_id、line、start、end、text、section、kind；text为来源精确子串。中文句末拆分且每个实质行都有单元；复杂子主张在审阅解释中继续细分。提取有问题应修正提取输入并建立新版本，不能悄悄重写来源来迎合结果。

新增用户回答：`workflow.py add-source --run-dir <目录> --kind followup --file <回答.txt>`。附件提取文本用 artifact；必须先检查提取。新来源使聚焦复核回到pending，更新相关分析后再完成复核。

## evidence.json

列表，每项必填：

```json
{
  "id": "E1", "source_id": "RESUME", "unit_id": "RESUME-U001",
  "quote": "必须是该单元中的精确原句或子串",
  "status": "self_reported", "actor": "individual",
  "action": "此处概括原文实际动作", "deliverable": "原文所述产物或未知",
  "completion": "actual", "metrics": []
}
```

status：self_reported/user_confirmed/artifact_supported/unclear/conflicting。user_confirmed 必须关联 followup；artifact_supported 必须关联 artifact。actor：individual/team/shared/unknown，表示所引动作主体而非项目全量所有权。completion：actual/expected/in_progress/unknown。指标可记录 value/unit/baseline/period/scope，所有数值保留来源口径。用户补充确认不等同外部核验。

## requirements.json

列表，每项：id、role、basis（jd/sample_jd/role_standard/hypothesis）、source_unit_ids、basis_note、description、task、responsibility、decision_depth、importance（core/supporting/bonus/hard）、support（direct/transferable/partial/unknown/missing/conflicting）、evidence_ids。

JD断言必须引用用户JD单元；sample_jd必须引用检索JD单元；方向标准/假设必须写 basis_note 的依据和局限。hard只用于实际用户JD或检索JD的明示条件，且只适用于被引用的具体岗位；；原文没有说明不能推断为硬门槛。positive支持须引用证据；missing只能配有明确条件冲突或经用户确认的缺口诊断，否则用unknown。

## diagnosis.json

列表，每项：id、scope（role/document/fact）、gap_type、requirement_ids、evidence_ids、demonstrates、does_not_demonstrate、impact、question（可空）、next_action。

gap_type与 `diagnosis.md` 一致。角色差距必须引用要求。experience_gap/depth_gap 另需 confirmed_by_user=true 和 confirmation_evidence_ids，引用用户回答来源；尚未确认用 evidence_missing。每条诊断的推导都应能对照原文检查，不仅填写栏目。

## sentence_review.json

`run.report_overview`可增加assessment（非空列表），每项包含dimension、status（met/partial/unknown/unmet）、judgment、requirement_ids和evidence_ids。前两种呈现为基本达标/部分达标，其余为尚不能判断/不符合；引用不能为空且必须存在。使用时同时给fit_scope与eligibility，分别说明样本范围、综合结论与资格约束。headline直接给申请判断，introduction解释优劣与行动；旧evidence_summary/gap_summary保留作内部记录，前台不重复展示。

列表，每项：id、unit_ids、decision、reason、capability、role_relevance、diagnosis_ids、evidence_ids、text、question。

每个简历单元恰好进入一个处理项，merge可关联多个单元。decision：keep/rewrite/merge/compress/drop/needs_input。keep的text为空或精确原文；rewrite/merge/compress的text为忠实可用表达且引用证据；needs_input须给具体question，可附保守表达。原句中的子主张及段落因果关系在reason解释。客观字段的capability可写“客观信息，不单独推断能力”，role_relevance说明简短用途。

核心经历的text可用“【具体主题】压缩STAR正文”，32字以内的前置主题在HTML中加粗；主题是text的一部分，同样参与数字与贡献检查。不要为标题另造未经核实的能力标签。reason解释本句价值、叙事重排与证据边界，不能只写压缩或待核实。

## 校验边界

校验器检查来源哈希与单元、ID引用、全量覆盖、模式、明显新增数字与贡献词、部分状态升级和确认来源，阻止损坏/缺失数据交付。数值和词语检查是保守辅助；可能要求改写词语以贴合来源，不是语义真实性证明。程序不能证明岗位标准准确、能力推断成立或所有同值数字含义相同，这些必须在聚焦审阅和人工抽检中验证。

验证：`workflow.py validate --run-dir <目录>`。正式HTML：`render_report.py <目录> --output-dir <输出目录>`。校验失败不会生成HTML；已有报告不被当成新版本交付。`snapshot`保存六文件快照，不写入其他候选人的目录。

## v2.1 扩展：共享诊断、检索来源与展示范围

新建目录 schema_version=2.1；旧 v2.0 目录继续兼容，不因新增字段被拒绝。

- `run.display_mode`：focused（默认）或 full。完整运行仍覆盖所有简历单元；展示只改变明细的组织，不能减少内部审阅。局部任务无需使用全量文件导出流程。
- `diagnosis.issue_key`：同一事实对象、根因和解决动作的稳定键，不同记录不得重复；同一根因跨句跨要求复用同一个 ID。`priority` 为 high/medium/low。程序只能检出重复键，语义重复仍需复核。
- `sentence_review.reason`：编辑动作与取舍，不再复制岗位差距的推导。关联诊断后，报告将诊断中的核实问题展示一次；修改项链接到有意义的诊断标题。needs_input 的 question 仍保留以便独立审计。
- `run.market_search`：`status` 为 pending（未完成，阻止交付）/complete/partial/failed/not_needed，`limitations` 为局限，`attempts` 为检索记录列表，每项 role、query、searched_at（ISO日期时间）、outcome。partial/failed 必须披露局限；无 JD 却 not_needed 必须注明用户拒绝联网或任务无需检索的原因。工具缺失未执行搜索时 outcome 如实写明，query 以“未执行：”开头。complete 仅表示本轮计划完成，不代表统计完整或实时有效。
- `sources.kind=jd_sample`：新增已读取的公开 JD，使用 add-jd 导入。metadata 必含 url（HTTP(S) 原始招聘链接）、role、title、company、location、level、published_at、retrieved_at（ISO日期时间）、availability（open/closed/unknown）。未知元数据写 unknown；open 需要实际页面状态依据，不能仅凭能访问。正文继续按哈希和精确单元校验。
- `requirements.basis=sample_jd`：source_unit_ids 必须指向 jd_sample 原文且 metadata.role 与要求 role 一致。basis_note 写样本范围与局限。hard 只对所引用的具体 JD 有效；跨公司常见要求保留引用，不泛化为方向硬门槛。招聘来源不作为候选人贡献证据。
- v2.1 `role_options` 在原有字段外，增加 transfer_difficulty、next_action、jd_source_ids（同方向 jd_sample ID 列表）。没有可读样本时必须给 search_limitation。检索失败可以交付边界明确的方向评估，不能伪装真实 JD 支持。

add-jd 示例：

```text
python <plugin-root>/scripts/workflow.py add-jd --run-dir <目录> --file <已读取JD.txt> --url <原链接> --role 产品实习 --title 产品经理实习生 --company <公司> --retrieved-at 2026-10-20 --location 上海 --level 实习 --availability unknown
```

add-jd 不访问网络，不把搜索摘要补写成岗位正文；添加来源后使状态回到 draft，须更新相关判断并重新复核。单 URL 去重由脚本检查；不同 URL 的同一职位由助手按公司、名称、地点和正文去重。

## v2.1 展示补充

role_options可选recommended_jd_source_ids，必须是该方向jd_source_ids的子集，不能包含closed来源；用于精简岗位推荐，不改变检索总样本。逐句的reason和question必须就当前原文写出，不依赖渲染器复制全局诊断；diagnosis_ids继续用于内部追溯。每个审阅只保留一个折叠，内含原文、改后、原因与建议，完整依据留在运行记录。

## 个人信息覆盖

姓名、联系方式、教育与日期信息同样生成原文单元并审阅。校验不因出现邮箱或手机号而阻断；只检查来源、引用、覆盖与事实改写。无法仅凭格式证明电话或邮箱可用，不擅自把显示地址改成另一事实地址。
