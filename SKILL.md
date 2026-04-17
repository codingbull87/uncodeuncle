---
name: report-illustrator
description: >
  将长篇 Markdown 产业报告重构为咨询风 HTML 报告，并导出分页合理、
  放大仍清晰的 PDF。适用于 8,000-20,000+ 字行业研究、公司研究、
  战略分析和投资分析报告。
metadata:
  author: zheliu
  updated: 2026-04-17
---

# Report Illustrator

## 目标

把纯 Markdown 长报告转成两类交付物：

1. `{report_name}_illustrated.html`：可离线打开、图文混排、咨询风排版
2. `{report_name}_illustrated.pdf`：通过 Chromium 打印引擎导出，文字和 SVG 图表尽量保持矢量清晰，分页尽量自然

不要使用 `html2canvas + jsPDF + JPEG` 作为最终 PDF 链路。该链路会把页面变成长图再切页，既不是矢量，也容易截断段落和图表。

## 核心原则

- LLM 负责理解报告、提炼观点、抽取数据、选择图表和图解类型
- 模板和脚本负责稳定的 HTML、CSS、分页、并排布局和 PDF 导出
- 每张图只回答一个问题
- 标题必须是结论句，不写“XX 分析”式标签
- 图表数量要足够丰富，但不能为了插图而插图
- 数据图、结构图、观点卡、矩阵、时间线、热力、路线图和表格要混合使用
- PDF 以浏览器打印为准，ECharts 必须使用 `renderer: 'svg'`
- 报告正文是已确认内容，视觉调整通过 `RECOMMENDATIONS.md` 完成

## 文件结构

```text
{report_dir}/
├── report.md
├── content.html
├── DESIGN_BRIEF.md
├── DESIGN_BRIEF.json
├── RECOMMENDATIONS.json
├── RECOMMENDATIONS.md
├── LAYOUT_PLAN.json
├── VALIDATION.md
├── PDF_QA.json
├── libs/
│   └── echarts.min.js
├── chart-fragments/
│   ├── C1.html
│   ├── C2.html
│   └── ...
├── {report_name}_illustrated.html
└── {report_name}_illustrated.pdf
```

Skill 目录提供：

```text
agents/
├── openai.yaml
├── orchestrator.md
├── planner.md
├── validator.md
└── fragment-generator.md
scripts/
├── assemble.py
├── check_phase_contract.py
├── lint_fragments.py
├── qa_html.py
├── qa_pdf.py
├── run_pipeline.py
├── run_pipeline_parallel.py
└── export_pdf.py
templates/
├── prompts/generator-task.md
├── prompts/validator-task.md
└── static/
    ├── css/
    │   └── README.md
    ├── base-styles.css
    └── pdf-export.js
libs/
└── echarts.min.js
references/
├── component-contracts.json
├── echarts-config.md
└── style-guide.md
```

## 推荐工作流

### 执行硬约束（不可违反）

- 必须按 `Phase 0 -> 1 -> 2 -> 3 -> 5 -> 6 -> 7 -> 8` 顺序执行，不允许跳阶段
- Phase 5 只做验证并写 `VALIDATION.md`，禁止在 Phase 5 生成任何 `chart-fragments/*.html`
- 只有 `VALIDATION.md` 判定为 `PROCEED` 时才允许进入 Phase 6
- 只有 `DESIGN_BRIEF.json` 包含 `color_confirmed: true` 且 `color_candidates` 至少 3 个时才允许进入 Phase 6
- 图表片段文件名必须是 `chart-fragments/C{id}.html`，禁止 `chart_01_xxx.html` 等自定义命名
- Phase 7 只能调用 `python3 {skill_dir}/scripts/assemble.py ...`，禁止写自定义组装器（如 `assemble_final.py`）
- Phase 8 只能调用 `python3 {skill_dir}/scripts/export_pdf.py ...`，禁止直接调用 Chrome `--print-to-pdf` 或探测/调用 `soffice`、LibreOffice
- 任一阶段脚本失败时必须停止并报告错误，不得发明替代流程继续

### Subagent 调度协议（显式角色）

本 skill 支持显式 subagent，采用“默认串行 + Phase 6 有限并行”的混合模式。

- `agents/orchestrator.md`：主调度者，负责门禁、分发、收口
- `agents/planner.md`：只负责 `DESIGN_BRIEF.md`、`RECOMMENDATIONS.*`
- `agents/validator.md`：只负责 `VALIDATION.md`
- `agents/fragment-generator.md`：一次只生成一个 `chart-fragments/C{id}.html`

强约束：

- 主线程必须做总控和门禁，subagent 只做各自职责范围内的文件
- Phase 0/1/2/3/5/7/8 必须串行执行，禁止并行
- 仅 Phase 6 允许并行：以“批次”为单位并行生成多个片段（每个 subagent 只写自己分配的 `C{id}.html`）
- 每个并行批次结束后必须执行片段质量检查，失败则先修复再进入下一批
- 每个片段必须满足 `references/component-contracts.json` 对应类型的 DOM contract
- subagent 禁止组装、禁止导出、禁止写自定义组装器和非标准输出名

每个关键阶段前建议先执行门禁检查：

```bash
python3 {skill_dir}/scripts/check_phase_contract.py {report_dir} before-fragments
python3 {skill_dir}/scripts/check_phase_contract.py {report_dir} before-assemble
python3 {skill_dir}/scripts/check_phase_contract.py {report_dir} before-export
python3 {skill_dir}/scripts/lint_fragments.py {report_dir}
python3 {skill_dir}/scripts/qa_html.py {report_dir}
python3 {skill_dir}/scripts/qa_pdf.py {report_dir}/{report_name}_illustrated.html
```

推荐统一入口（自动带 gate）：

```bash
python3 {skill_dir}/scripts/run_pipeline.py {report_dir} {report_name}
```

并行入口（仅 Phase 6 并行，其余阶段保持串行门禁）：

```bash
python3 {skill_dir}/scripts/run_pipeline_parallel.py \
  {report_dir} {report_name} \
  --worker-cmd "<你的subagent执行命令模板，必须包含 {chart_id} 和 {report_dir}>" \
  --max-workers 3 \
  --batch-size 3
```

### Phase 0 - 准备工作区

确认输入 Markdown 报告路径和输出目录。复制 ECharts：

```bash
mkdir -p {report_dir}/libs
cp {skill_dir}/libs/echarts.min.js {report_dir}/libs/
```

### Phase 1 - Markdown 转正文 HTML

优先使用 pandoc：

```bash
pandoc {report.md} \
  -f gfm+smart \
  -t html \
  --wrap=none \
  --no-highlight \
  -o {report_dir}/content.html
```

要求：

- `content.html` 只能包含正文片段，不包含完整 `<html>`、`<head>`、`<body>`
- 不插入图表、不插入脚本、不插入样式
- 保留所有章节、表格、列表、引用和脚注
- 报告开头的 `h1 + blockquote` 由组装器转换为 `.report-cover`

### Phase 2 - 设计 Brief

读取完整 Markdown，先写 `DESIGN_BRIEF.md`。它用于约束全篇，而不是约束单张图。
同时输出 `DESIGN_BRIEF.json`（包含至少 `color_scheme` 字段，供后续脚本读取）。

必须包含：

- 报告类型和读者
- 3-5 条核心叙事线
- 推荐视觉密度
- 推荐类型组合
- 调色板代号（从 `references/color-palettes.md` 中选择最合适的 1 个）
- 不适合使用的图表类型
- 分页风险提示

示例：

```markdown
# Design Brief

- 报告类型：公司研究 / 投资价值分析
- 读者：个人投资者和股票新手
- 叙事线：盈利拐点、估值修复、竞争风险、现金流纪律
- 视觉密度：30-36 个组件
- 类型组合：数据图 45%，结构图 35%，KPI/观点卡 20%
- 调色板：**A. Consulting Classic**（深蓝+深金，适合严肃商务交付）
```

#### 配色选择步骤（Phase 2 末尾执行）

读取 `references/color-palettes.md`，根据报告内容/行业/语气，从 5 个白底正式报告视觉系统中选择最合适的 3 个呈现给用户。

**硬约束：** 本 skill 面向正式报告，不面向网页换肤。候选 palette 必须保持白色页面底板，配色只影响标题点缀、表格线、关键数字、图表系列色和语义状态。禁止推荐深色底、大面积品牌色底、渐变底或营销页式 palette。

**路由参考：**
- 战略研究/投资判断/咨询交付 → **A. Consulting Classic** (`consulting-classic`)
- 企业级/机构级/技术平台报告 → **B. Institutional Carbon** (`institutional-carbon`)
- 董事会摘要/文字密集/财务页 → **C. Banker Monochrome** (`banker-monochrome`)
- 金融/订阅/收入模型/ARPU → **D. Financial Blue** (`financial-blue`)
- 消费品牌/战略评论/高层叙事页 → **E. Burgundy Editorial** (`burgundy-editorial`)

呈现格式：

```
配色候选（请选一个，或告诉我要调整）：

[A] Consulting Classic — 深蓝+深金，咨询交付密度
[B] Institutional Carbon — 企业蓝+冷灰，系统化机构风
[D] Financial Blue — 信任蓝+语义红绿，适合收入模型/订阅业务

当前默认：[A]
```

用户回复编号（A/B/C/D/E）或直接给方向词。选完后，在 `DESIGN_BRIEF.md` 末尾写入：

```markdown
- 调色板：A. Consulting Classic
```

并在 `DESIGN_BRIEF.json` 中写入对应字段：

```json
{
  "color_scheme": "consulting-classic",
  "color_confirmed": true,
  "color_selected_by": "user",
  "color_candidates": ["consulting-classic", "institutional-carbon", "financial-blue"]
}
```

如果用户还没有确认，只能写 `color_confirmed: false`，并停止在 Phase 2，不允许继续生成推荐项、片段、HTML 或 PDF。

Phase 3 及后续所有阶段必须读取 `DESIGN_BRIEF.json` 的 `color_scheme` 字段，从 `references/color-palettes.md` 中加载对应色板，不再使用任何写死的硬编码色值。

### Phase 3 - 生成视觉计划

输出两个文件：

- `RECOMMENDATIONS.json`：机器可读，用于片段生成
- `RECOMMENDATIONS.md`：人类可读，用于最终审阅和调位置

`RECOMMENDATIONS.json` 必须是 JSON 数组。每条推荐项：

```json
{
  "id": "1",
  "enabled": true,
  "type": "bar_compare",
  "anchor": "竞争格局：自主高端品牌与传统豪华品牌正面交锋",
  "anchor_occurrence": 1,
  "position": "after_first_paragraph",
  "layout": "full",
  "group": "",
  "row_title": "",
  "equal_height": false,
  "title": "2025 年交付量差距收窄，高端新能源进入正面对抗阶段",
  "data": {
    "labels": ["蔚来", "理想", "宝马中国", "奔驰中国"],
    "datasets": [
      { "name": "2025 交付量（万辆）", "values": [28.5, 50.1, 72.0, 68.4] }
    ],
    "unit": "万辆",
    "source": "公司公告、行业公开数据"
  },
  "notes": "自主高端品牌已经进入传统豪华品牌核心价格带",
  "priority": "high",
  "size": "medium"
}
```

字段规则：

- `id`：纯数字字符串，兼容 `C1`，但不要写成 `CC1`
- `enabled`：`false` 时组装器跳过
- `type`：使用下方图表类型
- `anchor`：纯标题文本，不带 `#`
- `anchor_occurrence`：同名标题出现多次时指定第几次，默认 1
- `position`：`after_cover`、`after_heading`、`after_first_paragraph`、`before_heading`、`section_end`
- `layout`：`full`、`half`、`third`、`compact`
- `group`：同锚点同位置的小组件可以组成并排视觉行
- `group_anchor` / `row_anchor`：可选；当并排组件来自不同小节但需要放到同一行时，使用共同锚点统一插入位置
- `row_title`：并排视觉行标题
- `equal_height`：默认 `false`；需要左右外框齐平时设为 `true`，组装样式只拉齐外层卡片，并压缩小组件内部尺度；不要让 KPI 网格、观点卡网格等内部内容区强行 `height: 100%`
- `title`：结论句，必须含观点判断
- `data.source`：尽量填写来源
- `size`：`small`、`medium`、`large`，用于控制分页风险

`RECOMMENDATIONS.md` 使用 v2 storyboard 格式，便于人类修改：

```markdown
<!-- report-illustrator-plan:v2 -->

# Visual Storyboard

## C1
enabled: true
type: kpi_strip
anchor: 第零章：执行摘要
anchor_occurrence: 1
position: after_heading
layout: full
group:
row_title:
equal_height: false
size: medium
title: 盈利拐点、估值低位与竞争窗口构成 2026 投资主线
why: 放在正文开始处，承接执行摘要，不插入封面内部。

## C2
enabled: true
type: bar_compare
anchor: 费用控制成效
anchor_occurrence: 1
position: after_heading
layout: half
group: cost-discipline
row_title: 费用纪律需要同时看研发和销售两条线
equal_height: true
size: small
title: 研发与销售费用同比大幅下降，费用基数明显收缩
why: 可与 C3 并排，避免两个小柱图连续占满整页。
```

组装器优先读取 `RECOMMENDATIONS.md` 的 storyboard 字段，再回退到 `RECOMMENDATIONS.json`。因此人工只需改 `enabled`、`anchor`、`position`、`layout`、`group`、`row_title`、`equal_height`、`size` 等字段，即可影响最终 HTML 的插入和排版。

`LAYOUT_OVERRIDES.json` 是自动修复产物，不是人工主编辑面。它应由 `repair_layout.py` 每轮重建；需要长期保留的排版意图，应回写到 `RECOMMENDATIONS.md/.json`。

### Phase 3.5 - 页面级排版计划

`assemble.py` 会在组装 HTML 时同步输出 `LAYOUT_PLAN.json`。该文件是机器生成的页面级排版骨架，用于记录每个视觉块的：

- `page_role`：`figure_text`、`paired_visual`、`table_visual`、`kpi_visual`
- `keep_with_next`：是否倾向于和后续正文绑定
- `can_shrink`：PDF 微调时是否允许缩小
- `max_shrink_ratio`：最大缩小比例，避免图表被压得过矮
- `group` / `row_layout` / `equal_height`：并排视觉行的版式信息

排版原则：

- 普通正文页底部空白应尽量控制在 15%-18% 以内
- 图文页底部空白可放宽到约 20%-22%
- 大段留白应主要出现在章节转场，而不是普通正文页随机出现
- PDF 导出阶段只做微调，不应任意大幅压缩图表
- 并排卡片必须遵循同一套 header/body/footer 协议，外框、内容起点和底部基线都要尽量对齐
- 若多个 recommendation 使用同一 `group` 但没有生成 `.visual-row`，必须视为布局失败并修正锚点/位置

### Phase 4 - 图表密度与类型选择

长报告推荐密度：

| 报告长度 | 推荐视觉组件数 | 说明 |
| --- | ---: | --- |
| 5,000-8,000 字 | 12-20 | 标准图文混排 |
| 8,000-15,000 字 | 20-35 | 咨询报告密度 |
| 15,000 字以上 | 30-50 | 高图解密度，必须控制重复 |

每个主要二级章节至少 1 个视觉组件。内容很长的章节可 2-4 个，但同一章节不要连续堆叠多个大图。

图表类型：

| type | 用途 |
| --- | --- |
| `kpi_strip` | 3-5 个关键数字 |
| `bar_compare` | 多对象大小差距 |
| `bar_trend` | 年度/季度趋势 |
| `line_trend` | 连续趋势或比例变化 |
| `waterfall` | 利润、成本、估值或收入桥 |
| `benchmark_table` | 精确指标对比 |
| `risk_matrix` | 风险概率 x 影响 |
| `matrix_2x2` | 竞争定位、优先级、战略取舍 |
| `timeline` | 政策、产品、技术或行业阶段 |
| `value_chain` | 产业链、利润池、价值迁移 |
| `issue_tree` / `driver_tree` | 原因拆解、增长驱动、问题树 |
| `range_band` / `football_field` | 估值区间、情景区间 |
| `heatmap` | 风险或机会热力 |
| `roadmap` | 产品、技术、渠道节奏 |
| `scorecard` | 投资判断或竞争力打分 |
| `decision_tree` | 策略分支或投资结论 |
| `sankey` | 流量、资金、成本或用户路径 |
| `tree` | 层级结构 |
| `gauge` | 单一完成率 |
| `insight_cards` | 从长段落中提炼 2-5 个重点观点 |

旧类型兼容：

- `callout` -> `kpi_strip`
- `chart-bar` -> `bar_compare` 或 `bar_trend`
- `chart-line` -> `line_trend`
- `table` -> `benchmark_table`

类型分布建议：

- 数据图：40%-55%
- 结构图/矩阵/时间线/热力/路线图：25%-40%
- KPI/观点卡/scorecard：15%-25%
- 表格：只在读者需要精确查数时使用

避免超过 60% 都是柱状图。

### Phase 5 - 验证视觉计划

按 `templates/prompts/validator-task.md` 执行验证，写入 `VALIDATION.md`。

严格边界：

- 本阶段只能读文件并输出 `VALIDATION.md`
- 禁止生成或改写 `chart-fragments/*.html`
- 禁止调用 `assemble.py`、`export_pdf.py`、Chrome 直出 PDF

必须检查：

- `RECOMMENDATIONS.json` 可解析
- `RECOMMENDATIONS.md` 是否是 v2 storyboard
- ID、type、anchor、title、data 合法
- anchor 在 Markdown 标题中存在
- 重复 anchor 是否有 `anchor_occurrence`
- 类型分布和视觉密度是否合理
- 是否存在封面内插图风险
- 并排组是否合理
- 如果已有片段，片段是否使用 SVG renderer

判定：

- `PROCEED`：进入 Phase 6
- `NEEDS_ITERATION`：修复推荐项或片段后重新验证
- `NEEDS_CLARIFICATION`：需要用户补充信息

进入 Phase 6 前先执行：

```bash
python3 {skill_dir}/scripts/check_phase_contract.py {report_dir} before-fragments
```

### Phase 6 - 生成图表片段

每条 recommendation 生成一个片段：

```text
{report_dir}/chart-fragments/C{id}.html
```

使用 `templates/prompts/generator-task.md`。

硬约束：

- 不写完整 HTML，只写片段
- 不使用 CDN
- ECharts 必须 `renderer: 'svg'`
- `animation: false`
- 柱状图必须有圆角
- 不包含 `html2canvas`、`jspdf`、`downloadChart`、下载按钮
- 图表高度尽量控制在 220-360px，大型结构图不超过 560px
- 没有数据支撑时，不生成空图，改成观点卡、矩阵或表格
- 只允许输出到 `chart-fragments/C{id}.html`，禁止写入自定义命名文件
- 必须读取并遵守 `references/component-contracts.json`
- 禁止自创结构类名；只使用 `references/style-guide.md` 和 `component-contracts.json` 中登记的类
- ECharts option 必须通过 `getComputedStyle` 读取 CSS 变量值；禁止直接写 `'var(--color-primary)'`
- 片段正文和脚本中禁止硬编码随机 hex 色值；调色板变量定义除外

### Phase 7 - 组装 HTML

执行：

```bash
python3 {skill_dir}/scripts/assemble.py {report_dir} {report_name}_illustrated
```

先执行：

```bash
python3 {skill_dir}/scripts/check_phase_contract.py {report_dir} before-assemble
```

更推荐直接执行统一入口：

```bash
python3 {skill_dir}/scripts/run_pipeline.py {report_dir} {report_name}
```

脚本会：

- 读取 `content.html`
- 优先读取 `RECOMMENDATIONS.md` v2 storyboard，fallback 到 `RECOMMENDATIONS.json`
- 清洗片段中的非法 `<p><div>` 嵌套和旧下载逻辑
- 把开头 `h1 + blockquote` 转换为 `.report-cover`
- 避免把视觉组件插入封面内部
- 根据 anchor、`anchor_occurrence`、`position` 注入片段
- 根据 `layout`、`group`、`row_title` 生成并排视觉行
- 注入固定 CSS 和打印按钮脚本
- 输出 `{report_name}_illustrated.html`
- 打印验证摘要

组装后必须执行：

```bash
python3 {skill_dir}/scripts/qa_html.py {report_dir}
```

看到 `[WARN]` 时要检查具体条目，不能假装成功。

禁止行为：

- 不得写 `assemble_final.py` 或其他临时组装器替代 `assemble.py`
- 不得改写输出命名为 `report_final.html` 这类非标准名

### Phase 8 - 导出 PDF

推荐使用脚本导出：

```bash
python3 {skill_dir}/scripts/export_pdf.py \
  {report_dir}/{report_name}_illustrated.html \
  {report_dir}/{report_name}_illustrated.pdf
```

先执行：

```bash
python3 {skill_dir}/scripts/check_phase_contract.py {report_dir} before-export
```

导出前必须执行 PDF 布局 QA：

```bash
python3 {skill_dir}/scripts/qa_pdf.py \
  {report_dir}/{report_name}_illustrated.html \
  {report_dir}/PDF_QA.json
```

`qa_pdf.py` 会用 Chromium-family 浏览器测量打印态页面几何，检查普通页底部大段空白、低密度单图页和异常分页。

`qa_layout.py` 会先给块级内容注入临时 PDF marker，再通过真实 PDF 回读每个 block 的页码和页内位置。不要再用正文文本模糊匹配页码；页码归因必须来自 marker。

`run_pipeline.py` / `run_pipeline_parallel.py` 会把 `LAYOUT_OVERRIDES.json` 当成派生文件，在每次流水线起点删除旧值，并在 layout repair 后重新生成。非末页若仍存在 `LAYOUT_DIAGNOSIS.json.sparsePages`，流水线必须失败，不能继续导出。

该脚本会查找 Chrome、Chromium 或 Edge，并调用浏览器打印引擎生成 PDF。这样比截图式 PDF 更适合矢量文字、SVG 图表和分页。

HTML 中的“打印 / 导出 PDF”按钮仅调用浏览器打印面板，方便人工预览。

禁止行为：

- 禁止直接调用浏览器 `--print-to-pdf` 绕过 `export_pdf.py`
- 禁止探测或调用 `soffice`、LibreOffice、wkhtmltopdf 作为主导出链路

## 分页设计规则

- 用 `@page` 控制 A4 页边距
- 用 `break-inside: avoid` 避免视觉组件内部断页
- 标题设置 `break-after: avoid`，减少标题悬挂
- 图表尺寸要可控，不要生成超高单图
- 大型图解优先拆成多个小组件
- 表格过长时拆成多个主题表，不要让单表跨多页
- 每页尽量有正文和视觉锚点，不要连续多页只有文字或只有图
- 小组件可并排，复杂图独占整行

推荐尺寸：

| size | 高度 | 用途 |
| --- | ---: | --- |
| `small` | 80-220px | KPI、观点卡、小表、小柱图 |
| `medium` | 240-340px | 大多数数据图 |
| `large` | 380-560px | 产业链、矩阵、复杂结构 |

## 咨询风判断标准

合格图表：

- 读者 3 秒内知道观点
- 标题自带结论
- 图表不依赖正文才能理解
- 数值、单位、来源清楚
- 颜色表达语义
- 同一报告组件语言统一
- 没有装饰性网格、随机渐变和多余图例

不合格图表：

- 只是把数字机械画出来
- 标题是“趋势分析”“对比图”
- 数据来源不明
- 同一页出现多个重复柱状图
- 图表过高，导致 PDF 大面积空白或截断
- 把低信息量图表都强行铺满整行

## 常见问题

### 为什么不再用 html2canvas/jsPDF？

因为它会把 HTML 变成图片，再切成 PDF 页面。结果不是矢量，放大不清晰，也无法尊重 CSS 分页规则。

### 为什么 ECharts 要用 SVG？

浏览器打印 PDF 时，SVG 图表比 canvas 更容易保持清晰。canvas 本质是位图，适合网页交互，不适合作为最终咨询报告 PDF 的主输出。

### 图越多越好吗？

不是。目标是让长报告更容易阅读和理解。推荐用"数据图 + 结构图 + 观点卡 + 矩阵"的组合提高密度，而不是把所有数字都画成柱状图。

### 用户如何手动微调？

优先改 `RECOMMENDATIONS.md`：

- 改 `enabled` 可开关某张图
- 改 `anchor`、`anchor_occurrence`、`position` 可调插入位置
- 改 `layout`、`group`、`row_title` 可调并排关系
- 改 `equal_height` 可控制并排组件是否左右齐平；需要齐平时设为 `true`，但同时保持 `size: small`
- 改 `title`、`type` 后需要重新生成对应片段

不要直接改正文 HTML，正文应由原始 Markdown 重新生成。

### Phase 7 组装失败：C3-C6 找不到锚点

**症状**：`assemble.py` 报告 C3-C6 "找不到锚点"，但直接调用 `iter_heading_matches()` 能找到匹配。

**根本原因**：pandoc 将 Markdown 中的直引号 `"` (U+0022) 转换为 HTML 中的左弯引号 `"` (U+201C)。例如 `二、"学会"到底是什么` 在 Markdown 中经过 pandoc 转换后，HTML h2 文本变成 `二、"学会"到底是什么`（两个 U+201C/U+201D）。

而 `assemble_engine.py` 的 `iter_heading_matches()` 做的是 `strip_tags(heading_text) == anchor_text` 直接比较——**没有对 heading 文本做 normalize**，只对 anchor 做了 normalize_anchor（把弯引号变直引号）。所以 normalize 后的 anchor 和未 normalize 的 heading 文本永远无法匹配。

**验证方法**：在 Python 中直接调 `iter_heading_matches()`，会返回 1 个匹配（因为测试脚本对 heading 文本做了 strip）；但 assemble.py 报告 0 个匹配（因为它读的是原始 heading 文本）。

**修复方法**：

1. **先验证 JSON 可解析**：`python3 -c "import json; json.load(open('RECOMMENDATIONS.json'))"` —— 如果报错，先修 JSON 语法错误（常见：JSON 数组/对象元素缺逗号、属性值未加引号）

2. **确认 anchor 字节正确**：用 Python 验证 anchor 的原始 bytes 是否包含 U+201C（`\xe2\x80\x9c`）和 U+201D（`\xe2\x80\x9d`）：
   ```python
   with open("RECOMMENDATIONS.json") as f:
       recs = json.load(f)
   anchor = recs['components'][1]['anchor']  # C2 在 index 1
   print(anchor.encode('utf-8').hex())  # 应该有 e2809c 和 e2809d
   ```

3. **同步修改两个文件**：修改 `RECOMMENDATIONS.md` 后，必须同步修改 `RECOMMENDATIONS.json` 中对应组件的 `anchor` 字段。两者存储的是相同的 anchor 值，用 Unicode curly quotes。

4. **验证匹配**：修改后用 Python 直接测 `iter_heading_matches(html, anchor)` 确认返回非空，再跑 `assemble.py`。

**重要**：`assemble.py` 在组装（fragment injection）阶段读取的是 `RECOMMENDATIONS.json`（不是 `.md`）。因此调试 anchor 匹配时必须同时修改 `.json` 中的 anchor 字段，两者保持同步。`.md` 文件是给人类审阅和调整位置用的，assembly engine 解析 `RECOMMENDATIONS.json` 中的 `components` 数组获取 anchor 值。

## 参考文件

- `templates/prompts/generator-task.md`：单条图表片段生成规范
- `templates/prompts/validator-task.md`：推荐项和片段验证规范
- `templates/static/css/*.css`：分层样式（主来源）
- `templates/static/base-styles.css`：兼容快照（由 `python3 scripts/build_base_styles.py` 生成）
- `templates/static/pdf-export.js`：浏览器打印按钮与图表 resize
- `references/style-guide.md`：组件和版式规范
- `references/component-contracts.json`：机器可读组件 DOM contract，供 generator、validator、lint gate 使用
- `references/echarts-config.md`：ECharts SVG 图表规范
- `scripts/check_phase_contract.py`：阶段门禁与命名契约检查
- `scripts/lint_fragments.py`：图表片段质量红线检查
- `scripts/qa_html.py`：最终 HTML 结构、并排组、非法残留和协议漂移检查
- `scripts/qa_pdf.py`：打印态分页几何和页底空白检查
- `scripts/qa_layout.py`：基于真实 PDF marker 的 block 归因和稀疏页诊断
- `scripts/layout_probe.py`：layout probe 共用模块，负责 block marker、PDF 回读和页内占用统计
- `scripts/run_pipeline.py`：带门禁的组装+导出统一入口
- `scripts/run_pipeline_parallel.py`：Phase 6 并行批次生成 + 串行收口入口
- `agents/orchestrator.md`：显式总控 subagent 角色定义
- `agents/planner.md`：显式规划 subagent 角色定义
- `agents/validator.md`：显式验证 subagent 角色定义
- `agents/fragment-generator.md`：显式片段生成 subagent 角色定义
- `scripts/assemble.py`：HTML 组装器
- `scripts/export_pdf.py`：Chromium PDF 导出器
