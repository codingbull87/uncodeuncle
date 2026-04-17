# HTML/CSS 样式规范

本文件解释设计规则。实际样式以 `templates/static/base-styles.css` 为准。

## 视觉基调

- 白底报告页，屏幕模式保留轻微阴影，打印模式去掉阴影
- 主色为深青绿，正向为绿，风险为红，关键提醒为琥珀色，辅助比较可用蓝色
- 图表减少网格线，用直接数值标注替代读轴
- 圆角控制在 6px，保持咨询报告的克制感
- 不使用大面积渐变、装饰光斑或随机颜色

## 版式规则

- `h1` 用于报告标题，并和报告元信息一起包入 `.report-cover`
- `h2` 用于主要章节，左侧深青绿竖线
- `h3` 用于小节
- 段落设置 `orphans` / `widows`，减少孤行
- 图表、KPI、矩阵、观点卡使用 `break-inside: avoid`
- 小组件可用 `.visual-row` 并排，复杂图必须独占整行

## 报告封面

组装器会把开头的 `h1 + blockquote` 转为：

```html
<section class="report-cover">
  <h1>报告标题</h1>
  <div class="report-meta">
    <span class="report-meta-key">研究项目</span>
    <span class="report-meta-value">...</span>
  </div>
</section>
```

不要把任何 `.visual-block` 插入 `.report-cover` 内部。

## 标准组件

### 数据图容器

```html
<div class="chart-container">
  <div class="chart-header">
    <div>
      <div class="chart-kicker">竞争格局</div>
      <div class="chart-title">结论式标题</div>
    </div>
  </div>
  <div class="chart-annotation">关键解读</div>
  <div id="chart-C1" style="width:100%;height:300px;"></div>
  <div class="chart-src">单位：亿元 | 数据来源：公司公告</div>
</div>
```

### KPI

```html
<div class="kpi-block">
  <div class="kpi-card green">
    <div class="kpi-label">收入增速</div>
    <div class="kpi-val green">28<span class="kpi-unit">%</span></div>
    <div class="kpi-sub">连续三个季度回升</div>
  </div>
</div>
```

### 观点卡

```html
<div class="consulting-figure">
  <div class="figure-title">利润池正从硬件向服务迁移</div>
  <div class="insight-grid">
    <div class="insight-card">
      <div class="insight-card-title">硬件毛利承压</div>
      <div class="insight-card-body">价格竞争压缩单车利润。</div>
    </div>
  </div>
  <div class="figure-src">数据来源：报告正文整理</div>
</div>
```

### 2x2 矩阵

```html
<div class="consulting-figure">
  <div class="figure-title">优先级矩阵将机会分为四类</div>
  <div class="matrix-2x2">
    <div class="matrix-cell emphasis">
      <div class="matrix-cell-title">高吸引力 / 高可行性</div>
      <div class="matrix-cell-body">优先投入。</div>
    </div>
  </div>
</div>
```

### 风险热力图

```html
<div class="consulting-figure">
  <div class="figure-title">短期风险集中在销量节奏、费用纪律和现金流</div>
  <div class="heatmap-grid">
    <div class="heatmap-cell high">
      <div class="heatmap-title">销量不及预期</div>
      <div class="heatmap-body">固定成本摊薄压力上升。</div>
    </div>
  </div>
</div>
```

### 驱动树

```html
<div class="consulting-figure">
  <div class="figure-title">盈利拐点由三条线共同决定</div>
  <div class="driver-tree">
    <div class="driver-root">盈利拐点</div>
    <div class="driver-branches">
      <div class="driver-branch">
        <div class="driver-title">规模利用率</div>
        <div class="driver-body">固定成本摊薄。</div>
      </div>
    </div>
  </div>
</div>
```

### 估值区间

```html
<div class="consulting-figure">
  <div class="figure-title">估值更适合用区间表达</div>
  <div class="range-band">
    <div class="range-row">
      <div class="range-label">中性情景</div>
      <div class="range-track">
        <div class="range-fill" style="left:28%;width:34%;"></div>
        <div class="range-marker" style="left:48%;"></div>
      </div>
      <div class="range-value">核心区间</div>
    </div>
  </div>
</div>
```

### 路线图

```html
<div class="consulting-figure">
  <div class="figure-title">技术、产品和渠道需要同步推进</div>
  <div class="swimlane-roadmap">
    <div class="swimlane">
      <div class="swimlane-label">产品</div>
      <div class="swimlane-track">
        <div class="swimlane-milestone">新平台车型</div>
      </div>
    </div>
  </div>
</div>
```

## 并排布局

组装器负责生成 `.visual-row`，片段本身不要手写 `.visual-row`。

推荐项示例：

```yaml
layout: half
group: cost-discipline
row_title: 费用控制需要同时看研发和销售两条线
equal_height: true
```

并排使用原则：

- 两张小柱图、KPI、观点卡可以并排
- 三张以上仅用于信息很轻的卡片
- 坐标轴复杂、字段多、需要读数的图表不要并排
- 默认顶端对齐、自然高度
- 需要左右外框齐平时设置 `equal_height: true`，并保持 `size: small`
- 同高行只拉齐 `.chart-container` / `.consulting-figure` 外层；内部的 `.kpi-block`、`.insight-grid` 等网格保持自然高度，通过更小的 padding、字号和图表高度压缩比例，避免只是把内部网格强行拉高

## 打印/PDF

主流程使用 Chromium 打印引擎导出 PDF：

```bash
python3 scripts/export_pdf.py report.html report.pdf
```

不要用 html2canvas 截图。截图式 PDF 无法稳定分页，也不是矢量输出。

打印规则：

- `@page { size: A4; margin: 16mm 17mm 18mm; }`
- `.visual-block`、`.visual-row`、`.chart-container`、`.consulting-figure` 使用 `break-inside: avoid`
- 标题使用 `break-after: avoid`
- 大型图解高度不超过 560px
- 表格过长时拆成多张主题表
