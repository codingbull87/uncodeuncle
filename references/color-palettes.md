# Color Palettes — 调色板索引

> Phase 1 末尾，AI 根据报告内容筛选 3 个候选呈现给用户。
> 用户选完后，`color_scheme` 字段写入 `DESIGN_BRIEF.json`，后续所有阶段读取此字段。

## 调色板一览

| 代号 | 名称 | 定位 | 主色 | 适用场景 |
|------|------|------|------|----------|
| **A** | McKinsey Blue | 咨询报告经典 | `#1e3a5f` | 正式交付、投资判断、严肃商务 |
| **B** | Modern Slate | 科技/互联网 | `#0f172a` | AI报告、行业分析、产品介绍 |
| **C** | Warm Clay | 人文/轻商务 | `#3f2b1f` | 培训方法论、个人成长、文化观察 |
| **D** | Forest Green | 积极正向 | `#14532d` | 战略建议、增长判断、机会分析 |
| **E** | Minimal Light | 极简干净 | `#f8fafc` | 知识管理、笔记整理、学术风格 |

---

## A. McKinsey Blue — 咨询报告经典

商务严谨、蓝调主色、金色强调。

```css
:root {
  --color-primary: #1e3a5f;
  --color-primary-dark: #0f2340;
  --color-positive: #166534;
  --color-negative: #991b1b;
  --color-accent: #d97706;
  --color-secondary: #64748b;
  --color-border: #d1d5db;
  --color-bg: #ffffff;
  --color-surface: #f8fafc;
  --color-text: #111827;
  --color-text-secondary: #6b7280;
  --echarts-palette: #1e3a5f, #2563eb, #166534, #d97706, #991b1b;
}
```

---

## B. Modern Slate — 科技/互联网

近黑蓝底、翠绿正向、亮红负向、靛蓝强调。

```css
:root {
  --color-primary: #0f172a;
  --color-primary-dark: #020617;
  --color-positive: #059669;
  --color-negative: #dc2626;
  --color-accent: #6366f1;
  --color-secondary: #94a3b8;
  --color-border: #334155;
  --color-bg: #0f172a;
  --color-surface: #1e293b;
  --color-text: #f1f5f9;
  --color-text-secondary: #94a3b8;
  --echarts-palette: #0f172a, #6366f1, #059669, #f59e0b, #ef4444;
}
```

**注意**：Modern Slate 是深色主题。图表容器背景、表格背景需要用 `--color-surface`，正文背景用 `--color-bg`。

---

## C. Warm Clay — 人文/轻商务

暖棕主色、森绿正向、暗红负向、橙褐强调。

```css
:root {
  --color-primary: #3f2b1f;
  --color-primary-dark: #1c1009;
  --color-positive: #2d6a4f;
  --color-negative: #9b2c2c;
  --color-accent: #c2410c;
  --color-secondary: #78716c;
  --color-border: #d6d3d1;
  --color-bg: #fafaf9;
  --color-surface: #f5f5f4;
  --color-text: #1c1917;
  --color-text-secondary: #78716c;
  --echarts-palette: #3f2b1f, #2d6a4f, #9b2c2c, #c2410c, #78716c;
}
```

---

## D. Forest Green — 积极正向

深森绿主色、浅绿层次、琥珀强调。

```css
:root {
  --color-primary: #14532d;
  --color-primary-dark: #052e16;
  --color-positive: #15803d;
  --color-negative: #b91c1c;
  --color-accent: #b45309;
  --color-secondary: #6b7280;
  --color-border: #d1d5db;
  --color-bg: #ffffff;
  --color-surface: #f0fdf4;
  --color-text: #111827;
  --color-text-secondary: #6b7280;
  --echarts-palette: #14532d, #15803d, #166534, #b45309, #b91c1c;
}
```

---

## E. Minimal Light — 极简干净

石墨主色、森林绿正向、正红负向、棕黄强调。浅底无彩色系，干净克制。

```css
:root {
  --color-primary: #18181b;
  --color-primary-dark: #09090b;
  --color-positive: #15803d;
  --color-negative: #b91c1c;
  --color-accent: #b45309;
  --color-secondary: #71717a;
  --color-border: #e4e4e7;
  --color-bg: #fafafa;
  --color-surface: #f4f4f5;
  --color-text: #18181b;
  --color-text-secondary: #71717a;
  --echarts-palette: #18181b, #71717a, #15803d, #b45309, #b91c1c;
}
```

---

## CSS 变量说明

生成图表片段时，用 CSS 变量替代硬编码色值：

| 变量 | 用途 |
|------|------|
| `--color-primary` | 图表主色、柱状图默认色、标题 |
| `--color-primary-dark` | 深色标题、正文主色 |
| `--color-positive` | 正向数据、增长、改善 |
| `--color-negative` | 负向数据、风险、下降 |
| `--color-accent` | 关键数字强调、琥珀色标注 |
| `--color-secondary` | 辅助文本、图例、次要轴标签 |
| `--color-border` | 表格边框、分隔线 |
| `--color-bg` | 报告背景色 |
| `--color-surface` | 卡片/图表容器背景 |
| `--color-text` | 正文主色 |
| `--color-text-secondary` | 辅助说明文字 |

ECharts 的 `color` 数组使用 `--echarts-palette` 变量展开后的逗号分隔值。
