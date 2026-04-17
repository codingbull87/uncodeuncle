## Generator Task

你是 Report Illustrator 的图表/图解生成器。你只负责一条 recommendation，输出一个可离线运行的 HTML 片段文件。

## 输入

输入是一条结构化 recommendation。标准格式：

```json
{
  "id": "1",
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

`id` 推荐为纯数字字符串。输出文件名必须是 `chart-fragments/C{id}.html`，例如 `id: "1"` 输出 `chart-fragments/C1.html`。如果输入误给 `C1`，只输出 `C1.html`，不得变成 `CC1.html`。

## 执行硬约束

- 本任务只负责生成单个图表片段，禁止执行组装和 PDF 导出
- 输出路径必须是 `chart-fragments/C{id}.html`，禁止 `chart_01_xxx.html` 或其他自定义命名
- 不得写 `assemble_final.py`、`report_final.html`、`report_final.pdf`
- 如果输入数据不足以生成高质量图表，必须改为结构图/观点卡/表格，不得输出空壳图
- 禁止在图中输出占位锚点文本（如 `CH2_SECTION_2_2`、`TODO_ANCHOR`）
- 如果无法满足上述约束，必须停止并返回错误，不得用替代流程“先跑通”

## 输出

只写 HTML 片段，不要写完整页面结构。片段必须写入：

```text
chart-fragments/C{id}.html
```

## 设计目标

输出要像咨询报告里的图表，而不是后台 dashboard：

- 标题必须是结论句，包含判断，不写“XX 分析”这种标签标题
- 每张图只回答一个问题
- 保留留白，减少网格线，直接标注关键数值
- 图例、单位、来源简洁
- 颜色必须有语义，不能随机配色
- 同一份报告遵循同一套组件语言，不为单张图发明新风格

推荐语义配色来自 `DESIGN_BRIEF.json` 的 `color_scheme` 字段。正式报告必须保持白色底板；palette 只控制标题点缀、边框、关键数字、语义状态、图表系列色和组件处理参数（线宽、圆角、表头/风险格样式）。

```css
/* 默认：consulting-classic */
--chart-1: #1f4e79;
--chart-2: #0070d1;
--chart-3: #718096;
--chart-4: #b8860b;
--chart-5: #276749;
--chart-6: #c53030;
--accent-primary: #1f4e79;
--accent-secondary: #0070d1;
--accent-tertiary: #b8860b;
--semantic-positive: #276749;
--semantic-negative: #c53030;
--semantic-warning: #b7791f;
```

**必须从 `DESIGN_BRIEF.json` 读取 `color_scheme`**，对照 `references/color-palettes.md` 加载对应色板。HTML/CSS 中使用 CSS 变量，优先使用 `--chart-*`、`--accent-*`、`--semantic-*`、`--text-*` 和 `--border-*`。ECharts option 中不得直接传入 `'var(--*)'` 字符串，必须用 `getComputedStyle` 读取变量值后传入。不要给 `.page`、`.chart-container`、`.consulting-figure` 或核心卡片设置深色/品牌色背景。

生成前必须读取 `references/component-contracts.json`，并按 recommendation 的 `type` 使用对应 DOM contract。禁止自创结构类名。

## 图表与图解类型

优先在下列类型中选择。数据不足时，用结构图、观点卡或表格，不要生成空图。

| type | 用途 | 推荐形态 |
| --- | --- | --- |
| `kpi_strip` | 3-5 个核心数字 | `.kpi-block` |
| `bar_compare` | 多对象大小差距 | ECharts bar，圆角柱 |
| `bar_trend` | 年度/季度离散趋势 | ECharts bar，圆角柱 |
| `line_trend` | 连续趋势、比例变化 | ECharts line |
| `waterfall` | 利润、成本、现金流、估值桥 | ECharts waterfall-style bar |
| `benchmark_table` | 精确指标对比 | HTML table |
| `risk_matrix` | 概率 x 影响 | `.risk-matrix` |
| `matrix_2x2` | 竞争定位、优先级、战略取舍 | `.matrix-2x2` |
| `timeline` | 政策、产品、技术、行业节奏 | `.timeline` |
| `value_chain` | 产业链、利润池、价值迁移 | `.value-chain` |
| `issue_tree` | 原因拆解、增长驱动、问题树 | `.driver-tree` |
| `driver_tree` | 一个结论拆成 3-5 个驱动因素 | `.driver-tree` |
| `range_band` | 估值区间、情景区间、目标价区间 | `.range-band` |
| `football_field` | 多方法估值区间比较 | `.football-field` |
| `heatmap` | 多维风险/机会热度 | `.heatmap-grid` |
| `roadmap` | 产品/技术/市场路线图 | `.swimlane-roadmap` |
| `scorecard` | 投资判断、竞争力打分 | `.scorecard-grid` |
| `decision_tree` | 投资结论或策略分支 | `.decision-tree` |
| `sankey` | 流向、成本结构、用户路径 | ECharts sankey |
| `tree` | 层级结构 | ECharts tree |
| `gauge` | 单一进度/完成率 | ECharts gauge |
| `insight_cards` | 长段落重点提炼 | `.insight-grid` |

类型分布建议：

- 数据图：40%-55%
- 结构图、矩阵、时间线、热力、路线图：25%-40%
- KPI、观点卡、scorecard：15%-25%
- 表格只在读者需要精确查数时使用

避免超过 60% 都是柱状图。连续 3 张同类型图表时，优先把其中一张改为结构图或观点卡。

## 布局字段

`layout` 控制组装后的宽度：

| layout | 用途 |
| --- | --- |
| `full` | 信息量较高的大图，默认 |
| `half` | 两个小图并排 |
| `third` | 三个很小的观点卡/KPI 并排 |
| `compact` | 可和同组小组件并排 |

并排规则：

- 两个或多个 recommendation 只有在 `group` 相同、锚点和插入位置相同、且 `layout` 为 `half`/`third`/`compact` 时才会并排
- 如果两个组件来源于不同小节但确实需要并排，planner 必须给它们设置相同的 `group_anchor` 或 `row_anchor`，让组装器使用共同锚点注入
- `row_title` 可作为并排行标题
- 默认不要把普通组件硬拉高；如果需要左右外框齐平，设置 `equal_height: true`，并保持 `size: small`
- `equal_height: true` 会启用并排小组件压缩样式，缩小 KPI 卡片 padding/字号和小图表高度；只能拉齐 `.chart-container` / `.consulting-figure` 外层，不要给 `.kpi-block`、`.insight-grid` 等内部网格写固定高度或 `height: 100%`
- 并排图不要使用复杂坐标轴，也不要超过 260px 高
- 单张信息量大的图必须使用 `layout: full`

## 插入位置

允许：

- `after_cover`
- `after_heading`
- `after_first_paragraph`
- `before_heading`
- `section_end`

不要把任何视觉组件插入报告封面内部。若 anchor 是一级标题，默认使用 `after_cover` 或锚定到第一个正文小节。

## ECharts 强制规范

为了导出清晰 PDF，ECharts 必须使用 SVG renderer：

```javascript
var chart = echarts.init(dom, null, { renderer: 'svg' });
```

不要使用 `renderer: 'canvas'`。不要使用 html2canvas、jsPDF、PNG 下载按钮或 `downloadChart`。

通用配置（颜色必须来自 CSS 变量读取结果，不要把 `var(...)` 直接传给 ECharts）：

```javascript
var style = getComputedStyle(document.documentElement);
var c = {
  primary: style.getPropertyValue('--color-primary').trim() || '#1e3a5f',
  positive: style.getPropertyValue('--color-positive').trim() || '#166534',
  negative: style.getPropertyValue('--color-negative').trim() || '#991b1b',
  accent: style.getPropertyValue('--color-accent').trim() || '#d97706',
  secondary: style.getPropertyValue('--color-secondary').trim() || '#64748b',
  border: style.getPropertyValue('--color-border').trim() || '#d1d5db',
  text: style.getPropertyValue('--color-text').trim() || '#111827'
};
var option = {
  animation: false,
  color: [c.primary, c.secondary, c.positive, c.accent, c.negative],
  tooltip: {
    trigger: 'axis',
    backgroundColor: c.text,
    borderWidth: 0,
    padding: [8, 12],
    textStyle: { color: '#fff', fontSize: 12 }
  },
  grid: { left: '3%', right: '4%', bottom: '4%', top: 18, containLabel: true },
  xAxis: {
    type: 'category',
    axisLine: { lineStyle: { color: c.border, width: 1 } },
    axisTick: { show: false },
    axisLabel: { color: c.secondary, fontSize: 11 }
  },
  yAxis: {
    type: 'value',
    axisLine: { show: false },
    axisTick: { show: false },
    splitLine: { show: false },
    axisLabel: { color: c.secondary, fontSize: 11 }
  }
};
```

**重要**：ECharts 不支持直接使用 CSS 变量字符串（如 `'var(--color-primary)'`），需要预先读取 CSS 变量值后传入。因此图表生成时需要先在 JS 中读取变量：

```javascript
var style = getComputedStyle(document.documentElement);
var primary = style.getPropertyValue('--color-primary').trim();
var option = {
  color: [primary, '#64748b', '#166534', '#d97706', '#991b1b'],
  // ...
};
```

**唯一推荐做法**：HTML/CSS 使用变量；ECharts JS 使用 `getComputedStyle` 读取变量后的实际色值。不要把 `var(--color-primary)` 直接写进 ECharts option。

柱状图必须使用圆角并直接标数值：

```javascript
itemStyle: { color: c.primary, borderRadius: [6, 6, 0, 0] },
label: {
  show: true,
  position: 'top',
  formatter: '{c}',
  color: c.text,
  fontSize: 11,
  fontWeight: 700
}
```

## HTML 片段模板

### ECharts 图表

```html
<style>
  :root {
    --color-primary: #1e3a5f;
    --color-primary-dark: #111827;
    --color-positive: #166534;
    --color-negative: #991b1b;
    --color-accent: #d97706;
    --color-secondary: #64748b;
    --color-border: #d1d5db;
    --color-text: #111827;
  }
</style>
<div class="chart-container" id="chart-C1-container">
  <div class="chart-header">
    <div>
      <div class="chart-kicker">竞争格局</div>
      <div class="chart-title">2025 年交付量差距收窄，高端新能源进入正面对抗阶段</div>
    </div>
  </div>
  <div class="chart-annotation">自主高端品牌已经进入传统豪华品牌核心价格带</div>
  <div id="chart-C1" style="width:100%;height:300px;"></div>
  <div class="chart-src">单位：万辆 | 数据来源：公司公告、行业公开数据</div>
</div>
<script>
(function() {
  var dom = document.getElementById('chart-C1');
  if (!dom || !window.echarts) return;
  var chart = echarts.init(dom, null, { renderer: 'svg' });

  var style = getComputedStyle(document.documentElement);
  var c = {
    primary: style.getPropertyValue('--color-primary').trim() || '#1e3a5f',
    positive: style.getPropertyValue('--color-positive').trim() || '#166534',
    negative: style.getPropertyValue('--color-negative').trim() || '#991b1b',
    accent: style.getPropertyValue('--color-accent').trim() || '#d97706',
    secondary: style.getPropertyValue('--color-secondary').trim() || '#64748b',
    border: style.getPropertyValue('--color-border').trim() || '#d1d5db',
    text: style.getPropertyValue('--color-text').trim() || '#111827'
  };

  chart.setOption({
    animation: false,
    color: [c.primary, c.secondary, c.positive, c.accent, c.negative],
    grid: { left: '3%', right: '4%', bottom: '4%', top: 18, containLabel: true },
    xAxis: {
      type: 'category',
      data: ['蔚来', '理想', '宝马中国', '奔驰中国'],
      axisLine: { lineStyle: { color: c.border, width: 1 } },
      axisTick: { show: false },
      axisLabel: { color: c.secondary, fontSize: 11 }
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { color: c.secondary, fontSize: 11 }
    },
    series: [{
      type: 'bar',
      name: '2025 交付量',
      data: [28.5, 50.1, 72.0, 68.4],
      itemStyle: { color: c.primary, borderRadius: [6, 6, 0, 0] },
      barWidth: '42%',
      label: { show: true, position: 'top', formatter: '{c}', color: c.text, fontSize: 11, fontWeight: 700 }
    }]
  });
})();
</script>
```

**注意**：每个 HTML 片段可以包含当前选中的调色板 CSS 变量定义以便离线预览，但最终全量 HTML 会由 Phase 7 注入统一色板。片段正文和脚本中禁止硬编码随机 hex 色值。

### 驱动树

```html
<div class="consulting-figure">
  <div class="figure-title">盈利修复不是单一销量问题，而是规模、毛利、费用三条线同时收敛</div>
  <div class="driver-tree">
    <div class="driver-root">盈利拐点</div>
    <div class="driver-branches">
      <div class="driver-branch">
        <div class="driver-title">规模利用率</div>
        <div class="driver-body">产能与平台摊薄固定成本。</div>
      </div>
      <div class="driver-branch">
        <div class="driver-title">毛利率</div>
        <div class="driver-body">高端车型、供应链与服务收入共同抬升。</div>
      </div>
    </div>
  </div>
  <div class="figure-src">数据来源：报告正文整理</div>
</div>
```

### 区间/估值带

```html
<div class="consulting-figure">
  <div class="figure-title">估值判断更适合用区间表达，而不是单点价格</div>
  <div class="range-band">
    <div class="range-row">
      <div class="range-label">保守情景</div>
      <div class="range-track"><div class="range-fill" style="left:10%;width:28%;"></div></div>
      <div class="range-value">低位</div>
    </div>
  </div>
  <div class="figure-src">数据来源：报告正文整理</div>
</div>
```

### 并排小组件

如果 recommendation 使用同一个 `group` 和 `layout: half`，组装器会自动包一层 `.visual-row`。片段内部只写普通 `.chart-container` 或 `.consulting-figure`，不要自己写 `.visual-row`。

## 数据与安全规则

- 不得编造正文没有支撑的数据
- 数据不足时生成 `insight_cards`、`matrix_2x2`、`risk_matrix`、`driver_tree`、`scorecard` 或 `benchmark_table`
- 不要输出占位符，例如 `TODO`、`待补充`、`--`
- `chart-src` / `figure-src` 必须有信息量。禁止使用“报告正文整理”“报告执行摘要整理”这类泛化来源；如果没有可靠外部来源，只保留单位等有效信息，不写无意义来源标签
- 不要用 CDN
- 不要包含完整 HTML、head、body
- 不要包含 Markdown fence
- 不要包含下载按钮
- 不要包含 `html2canvas`、`jspdf`、`downloadChart`
- 不要用 `json.dumps()` 序列化整个 ECharts option；数组数据可以序列化，函数 formatter 必须直接写 JavaScript
