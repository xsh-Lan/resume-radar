# PDF 原件对照工作台

完整评估以可选中文字的 PDF 为输入，保留原文件。Word 先由用户另存为 PDF；扫描件、图片式 PDF 和加密文件提示换用文字版，不伪造识别结果。

完整求职任务依 `guided-workflow.md` 一次确定求职目标；已明确或委托的目标直接沿用。本文件负责原件、案例和结果报告，不增加方案、输出范围或事实追问关卡。

## 准备与分析

`ROOT` 是同时包含 `scripts/`、`standards/`、`skills/` 的安装目录。独立 skill 的入口位于 ROOT/SKILL.md；插件入口位于 ROOT/skills/resume-radar/SKILL.md。所有命令使用 ROOT 的实际绝对路径，不依赖当前工作目录。

1. 询问用户是否有意向职业方向；已有回答或 JD 时直接使用，不重复询问。没有意向时按统一入口探索和推荐，不强制进入岗位分类选择页。
2. 检查 Python 与 PyMuPDF 是否可用。缺少 PyMuPDF 时运行 `python -m pip install -r <ROOT>/requirements.txt`，失败则披露具体环境问题。
3. 初始化新的候选人与版本目录：

```text
python <ROOT>/scripts/workflow.py init --resume <原件.pdf> --run-dir <新运行目录> --candidate-key <候选人键> [--jd <已检查的JD.txt>] [--target <意向方向>] [--stage <职级>]
```

初始化保存 original.pdf、pdf-origin.json 和六份分析文件。读取 sources.json 中的完整文字，并查看 PDF 页面，检查多栏阅读顺序、符号和提取完整性。PDF 位置来自原件字符坐标，不从模型猜测矩形。提取有缺损时先解决来源问题，不篡改来源单元。需要辅助文本视图时可从 sources.json 导出，但保持原始来源不变。

4. 按岗位分析、事实核实、逐句编辑与聚焦复核完成数据契约。网页不负责调用模型；初始化和渲染都不等于已经分析。

## 固定示例关联

已移除原独立教学卡片机制。保留四个核心 skill 自带的方法与例子，不生成新的案例冒充固定库。Hired 固定库含 41 类产品经理岗位的 2,125 组案例，不能宣传为跨职业案例库或真实已核验履历。原库中的教学说明、事实边界与来源保留。

`run.example_library_scope` 写 `product_management` 或 `other`。多职业分析继续支持；非产品经理不强配产品经理案例。

产品经理目标下，按诊断涉及的真实任务查询，而不是只按标题、关键词碰撞认定适用：

```text
python <ROOT>/scripts/example_library.py --query <具体职责词>
python <ROOT>/scripts/example_library.py --case-id <查询得到的ID>
```

先实际阅读案例的完整内容，核对业务对象、本人责任和项目阶段。合适时新增 `example_links.json`：

```json
[
  {
    "review_id": "S4",
    "case_id": "从固定库查询得到的原始ID",
    "reason": "解释案例的哪一部分能帮助理解当前原句的问题",
    "conditions": "明确可参考的结构，以及不属于候选人的场景、责任、数字和结果"
  }
]
```

找不到适用案例则不关联，不能虚构案例 ID、扩大匹配范围或从案例复制候选人事实。用户自己的事实改写与固定库展示分开。

## 校验与交付

```text
python <ROOT>/scripts/workflow.py validate --run-dir <运行目录>
python <ROOT>/scripts/render_report.py <运行目录> --output-dir <运行目录>/report --open
```

确认 validation.json 的分析校验和 pdf_mapping。未能可靠定位的单元在报告中显示“原文位置待核对”，不把搜索猜测写成精确定位。案例引用和文件哈希错误会阻止生成。

报告顶部导航包括整体判断、模块诊断、逐句审阅、待补充事项、岗位要求、经历示例库。中间是原件各页，右侧是诊断与案例；编号和高亮双向对应，支持缩放。案例有工作经历、C-STAR、自然表达三种阅读方式。处理标记保存在当前浏览器，不能说成已修改 PDF 或已更新分析。

网页无需模型 Key、Chrome 扩展或在线服务，报告文件夹包含 HTML、本地案例脚本、页面图片和原 PDF。移动或分享报告时保留整个文件夹；安装 skill 的压缩包不包含候选人的简历、分析或浏览器状态。反馈回到 Codex 后，用新来源更新受影响的分析并再次复核、生成报告。
