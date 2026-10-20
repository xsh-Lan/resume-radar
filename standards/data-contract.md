# 运行数据契约 v2

目录由 `workflow.py init` 新建。输入为已提取并检查过的UTF8文本；脚本自动清理常见联系方式，可重复传入 `--redact-name`。姓名识别需要人工检查；不改原文件。初始化会生成以下六个JSON文件；空列表是待分析状态，不能直接交付。

## run.json

`schema_version`、`candidate_key`、`mode`由初始化确定。mode 为 jd/direction/explore。target_status 为 user_specified/user_selected/provisional/unresolved；暂定方向必须在 assumptions 披露依据与尚未确认内容。stage 是用户提供的职级或 unknown。

分析填入：summary（整体判断）、assumptions（字符串列表）、role_options（探索模式）、actions（行动）、final_text（请求全文改写时填写）、review（聚焦审阅）。分析与复核完成后将 status 改为 reviewed；追加来源后回到 draft，需再次复核。

role_options 每项：role、rationale、unknowns、evidence_ids。每个方向引用实际经历，选择服从用户目标；没有市场检索不声称在招、市场需求或录用概率。

actions 每项：type（edit/evidence/practice/decision）、text、diagnosis_ids。review 为 `{ "status": "completed", "findings": ["具体发现及关联ID；修正了什么或哪些仍未知"] }`。如无问题可为空列表；它记录本次内容审阅，不是外部证明。

正式报告建议填写 `report_overview`：headline（简短的核心判断，可用换行）、introduction（判断说明）、evidence_summary（已有经历依据）、gap_summary（关键证据缺口）、priorities（优先补充事项列表）。每项 priority 必须包含 title、text、diagnosis_ids，引用已存在的具体诊断。所有文案为已审阅结论的展示摘要，不新增事实、数据或岗位门槛。完整 summary 仍保存在“岗位方向与判断依据”内，避免为压缩首屏丢失限定条件。旧运行目录未填写此字段时，直接展示完整 summary 并使用既有行动，不自动推导新的能力判断。

## sources.json

`sources`包含来源对象：id、kind（resume/jd/followup/artifact）、text、sha256、units。脚本生成并保持不变。单元含 id、source_id、line、start、end、text、section、kind；text为来源精确子串。中文句末拆分且每个实质行都有单元；复杂子主张在审阅解释中继续细分。提取有问题应修正脱敏输入并建立新版本，不能悄悄重写来源来迎合结果。

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

列表，每项：id、role、basis（jd/role_standard/hypothesis）、source_unit_ids、basis_note、description、task、responsibility、decision_depth、importance（core/supporting/bonus/hard）、support（direct/transferable/partial/unknown/missing/conflicting）、evidence_ids。

JD断言必须引用JD单元；方向标准/假设必须写 basis_note 的依据和局限。hard只用于实际JD明示条件；原文没有说明不能推断为硬门槛。positive支持须引用证据；missing只能配有明确条件冲突或经用户确认的缺口诊断，否则用unknown。

## diagnosis.json

列表，每项：id、scope（role/document/fact）、gap_type、requirement_ids、evidence_ids、demonstrates、does_not_demonstrate、impact、question（可空）、next_action。

gap_type与 `diagnosis.md` 一致。角色差距必须引用要求。experience_gap/depth_gap 另需 confirmed_by_user=true 和 confirmation_evidence_ids，引用用户回答来源；尚未确认用 evidence_missing。每条诊断的推导都应能对照原文检查，不仅填写栏目。

## sentence_review.json

列表，每项：id、unit_ids、decision、reason、capability、role_relevance、diagnosis_ids、evidence_ids、text、question。

每个简历单元恰好进入一个处理项，merge可关联多个单元。decision：keep/rewrite/merge/compress/drop/needs_input。keep的text为空或精确原文；rewrite/merge/compress的text为忠实可用表达且引用证据；needs_input须给具体question，可附保守表达。原句中的子主张及段落因果关系在reason解释。客观字段的capability可写“客观信息，不单独推断能力”，role_relevance说明简短用途。

## 校验边界

校验器检查来源哈希与单元、ID引用、全量覆盖、模式、明显新增数字与贡献词、部分状态升级和确认来源，阻止损坏/缺失数据交付。数值和词语检查是保守辅助；可能要求改写词语以贴合来源，不是语义真实性证明。程序不能证明岗位标准准确、能力推断成立或所有同值数字含义相同，这些必须在聚焦审阅和人工抽检中验证。

验证：`workflow.py validate --run-dir <目录>`。正式HTML：`render_report.py <目录> --output-dir <输出目录>`。校验失败不会生成HTML；已有报告不被当成新版本交付。`snapshot`保存六文件快照，不写入其他候选人的目录。
