# ECharts 配置规范

最终 PDF 通过 Chromium 打印导出，因此 ECharts 必须优先使用 SVG renderer。

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

## 通用坐标轴

```javascript
color: ['#0f766e', '#2563eb', '#0f7a4f', '#b45309', '#b42318'],
grid: { left: '3%', right: '4%', bottom: '4%', top: 18, containLabel: true },
xAxis: {
  type: 'category',
  axisLine: { lineStyle: { color: '#d9e2ec', width: 1 } },
  axisTick: { show: false },
  axisLabel: { color: '#64748b', fontSize: 11 }
},
yAxis: {
  type: 'value',
  axisLine: { show: false },
  axisTick: { show: false },
  splitLine: { show: false },
  axisLabel: { color: '#64748b', fontSize: 11 }
}
```

## 柱状图

柱状图必须做圆角，并直接标注关键数值。

```javascript
series: [{
  type: 'bar',
  name: '收入',
  data: [492.7, 558.0, 631.8, 724.2],
  itemStyle: { color: '#0f766e', borderRadius: [6, 6, 0, 0] },
  barWidth: '42%',
  label: {
    show: true,
    position: 'top',
    formatter: '{c}',
    color: '#111827',
    fontSize: 11,
    fontWeight: 700
  }
}]
```

横向柱状图使用右侧圆角：

```javascript
itemStyle: { color: '#0f766e', borderRadius: [0, 6, 6, 0] }
```

## 折线图

```javascript
series: [{
  type: 'line',
  name: '毛利率',
  data: [14.2, 16.1, 17.5, 17.5],
  itemStyle: { color: '#0f7a4f' },
  lineStyle: { width: 2, color: '#0f7a4f' },
  symbol: 'circle',
  symbolSize: 6,
  label: {
    show: true,
    position: 'top',
    formatter: '{c}%',
    color: '#111827',
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
    itemStyle: {
      color: function(params) { return params.value >= 0 ? '#0f7a4f' : '#b42318'; },
      borderRadius: [6, 6, 0, 0]
    },
    label: { show: true, position: 'top', formatter: '{c}', color: '#111827', fontSize: 11, fontWeight: 700 }
  }
]
```

## 标注

关键点可用 `markPoint`：

```javascript
markPoint: {
  symbol: 'circle',
  symbolSize: 8,
  label: { formatter: '{b}', position: 'top', color: '#b45309', fontSize: 10 },
  data: [{ coord: [3, 724.2], name: '历史最高' }]
}
```

目标线可用 `markLine`：

```javascript
markLine: {
  silent: true,
  lineStyle: { color: '#b45309', type: 'dashed', width: 1 },
  data: [
    { yAxis: 700, label: { formatter: '目标 700 亿', position: 'end', color: '#b45309', fontSize: 10 } }
  ]
}
```

## 配色

| 语义 | 色值 |
| --- | --- |
| 主语/核心对象 | `#0f766e` |
| 深色标题 | `#111827` |
| 正向/增长 | `#0f7a4f` |
| 负向/风险 | `#b42318` |
| 辅助比较 | `#2563eb` |
| 关键标注 | `#b45309` |
| 辅助文字 | `#64748b` |
| 轴线/边框 | `#d9e2ec` |
