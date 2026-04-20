# ECharts 配置规范

最终 PDF 通过 Chromium 打印导出，因此 ECharts 必须优先使用 SVG renderer。这里的示例既要可用，也必须通过当前 lint 规则；如果示例本身会触发 lint，那参考文档就是坏文档。

## 初始化

```javascript
var dom = document.getElementById('chart-C1');
if (!dom || !window.echarts) return;
var chart = echarts.init(dom, null, { renderer: 'svg' });
```

必须设置：

```javascript
animation: false
```

禁止：

- `renderer: 'canvas'`
- html2canvas
- jsPDF
- PNG 下载按钮
- 依赖动画完成后才可读
- 在脚本中直接写 hex 色值
- 在脚本中写 `var(--color-*)`
- 在脚本中写 `|| '#888'` 之类的 hex fallback
- 在 `<style>` 中使用 `:host` 承载调色变量

## 颜色读取

ECharts `option` 不能直接使用 CSS 变量字符串，必须先读取实际值：

```javascript
var style = getComputedStyle(document.documentElement);
var c = {
  primary: style.getPropertyValue('--color-primary').trim(),
  secondary: style.getPropertyValue('--color-secondary').trim(),
  positive: style.getPropertyValue('--color-positive').trim(),
  negative: style.getPropertyValue('--color-negative').trim(),
  accent: style.getPropertyValue('--color-accent').trim(),
  border: style.getPropertyValue('--color-border').trim(),
  text: style.getPropertyValue('--color-text').trim(),
  inverseText: style.getPropertyValue('--color-inverse-text').trim()
};
```

片段内如果需要声明色板，只能放在 `<style>` 的 `:root` 中，不要使用 `:host`：

```html
<style>
  :root {
    --color-primary: #1e3a5f;
    --color-secondary: #64748b;
    --color-positive: #166534;
    --color-negative: #991b1b;
    --color-accent: #d97706;
    --color-border: #d1d5db;
    --color-text: #111827;
    --color-inverse-text: #ffffff;
  }
</style>
```

## 通用坐标轴

```javascript
color: [c.primary, c.secondary, c.positive, c.accent, c.negative],
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
```

## 柱状图

柱状图必须做圆角，并直接标注关键数值。当前 contracts 检查的是 `barBorderRadius`，不是泛化的 `borderRadius`。

```javascript
series: [{
  type: 'bar',
  name: '收入',
  data: [492.7, 558.0, 631.8, 724.2],
  barBorderRadius: [6, 6, 0, 0],
  itemStyle: { color: c.primary },
  barWidth: '42%',
  label: {
    show: true,
    position: 'top',
    formatter: '{c}',
    color: c.text,
    fontSize: 11,
    fontWeight: 700
  }
}]
```

横向柱状图使用右侧圆角：

```javascript
barBorderRadius: [0, 6, 6, 0]
```

## 折线图

```javascript
series: [{
  type: 'line',
  name: '毛利率',
  data: [14.2, 16.1, 17.5, 17.5],
  itemStyle: { color: c.positive },
  lineStyle: { width: 2, color: c.positive },
  symbol: 'circle',
  symbolSize: 6,
  label: {
    show: true,
    position: 'top',
    formatter: '{c}%',
    color: c.text,
    fontSize: 11,
    fontWeight: 700
  }
}]
```

## 瀑布图

用透明辅助柱实现 waterfall，不要把累计值误当单项贡献。

```javascript
series: [
  {
    type: 'bar',
    stack: 'total',
    itemStyle: { color: 'transparent', borderColor: 'transparent' },
    emphasis: { itemStyle: { color: 'transparent', borderColor: 'transparent' } },
    data: [0, 120, 70, 90]
  },
  {
    type: 'bar',
    stack: 'total',
    data: [120, -50, 20, 30],
    barBorderRadius: [6, 6, 0, 0],
    itemStyle: {
      color: function(params) { return params.value >= 0 ? c.positive : c.negative; }
    },
    label: { show: true, position: 'top', formatter: '{c}', color: c.text, fontSize: 11, fontWeight: 700 }
  }
]
```

## 标注

关键点可用 `markPoint`：

```javascript
markPoint: {
  symbol: 'circle',
  symbolSize: 8,
  label: { formatter: '{b}', position: 'top', color: c.accent, fontSize: 10 },
  data: [{ coord: [3, 724.2], name: '历史最高' }]
}
```

目标线可用 `markLine`：

```javascript
markLine: {
  silent: true,
  lineStyle: { color: c.accent, type: 'dashed', width: 1 },
  data: [
    { yAxis: 700, label: { formatter: '目标 700 亿', position: 'end', color: c.accent, fontSize: 10 } }
  ]
}
```

## 语义映射

建议语义而不是固定色值：

| 语义 | 变量 |
| --- | --- |
| 主语/核心对象 | `c.primary` |
| 深色标题/正文 | `c.text` |
| 正向/增长 | `c.positive` |
| 负向/风险 | `c.negative` |
| 辅助比较 | `c.secondary` |
| 关键标注 | `c.accent` |
| 轴线/边框 | `c.border` |
