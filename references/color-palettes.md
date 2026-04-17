# Report Palettes — 正式报告白底调色板

> 这些 palette 面向长篇 Markdown -> 正式 PDF/HTML 报告，不是网页主题。所有方案都必须保持白色页面底板；配色只影响标题点缀、表格线、关键数字、语义色和图表系列色。

## 调色板一览

| 代号 | `color_scheme` | 名称 | 定位 | 主强调色 | 适用场景 |
|------|----------------|------|------|----------|----------|
| **A** | `consulting-navy` | Consulting Navy | 咨询/投行交付 | `#1f4e79` | 战略研究、投资判断、正式交付 |
| **B** | `institutional-blue` | Institutional Blue | 企业级/机构级 | `#0f62fe` | 科技公司、平台业务、管理层报告 |
| **C** | `corporate-neutral` | Corporate Neutral | 通用商务 | `#2563eb` | 内部汇报、跨部门分析、培训材料 |
| **D** | `financial-trust` | Financial Trust | 金融/订阅/收入模型 | `#0052cc` | 金融、订阅、ARPU、商业模式分析 |
| **E** | `boardroom-green` | Boardroom Green | 增长/战略建议 | `#166534` | 增长机会、长期路线、经营改善 |
| **F** | `monochrome-executive` | Monochrome Executive | 极简高密度 | `#18181b` | 文字密集、董事会摘要、低装饰报告 |

## 白底硬规则

所有 palette 必须满足：

```css
--report-bg: #ffffff;
--report-surface: #ffffff;
--paper: #ffffff;
```

允许使用 `--report-subtle` / `--accent-soft` 作为浅色表头、隔行底、轻量强调区，但禁止把正文页、卡片主体、图表容器改成深色或品牌色底。

## A. Consulting Navy — 咨询/投行交付

源自 McKinsey Delivery 风格：白底、深蓝标题、蓝灰结构线、深金少量点缀。

```css
:root {
  --report-bg: #ffffff;
  --report-surface: #ffffff;
  --report-subtle: #f7f8fa;
  --report-subtle-2: #edf2f7;

  --text-primary: #1a202c;
  --text-secondary: #4a5568;
  --text-muted: #718096;
  --border-subtle: #e2e8f0;
  --border-strong: #cbd5e1;

  --accent-primary: #1f4e79;
  --accent-secondary: #0070d1;
  --accent-tertiary: #b8860b;
  --accent-soft: #ebf0f7;
  --accent-strong: #17365d;

  --semantic-positive: #276749;
  --semantic-negative: #c53030;
  --semantic-warning: #b7791f;
  --semantic-info: #2b6cb0;

  --chart-1: #1f4e79;
  --chart-2: #0070d1;
  --chart-3: #718096;
  --chart-4: #b8860b;
  --chart-5: #276749;
  --chart-6: #c53030;
  --echarts-palette: #1f4e79, #0070d1, #718096, #b8860b, #276749, #c53030;
}
```

## B. Institutional Blue — 企业级/机构级

源自 IBM / Enterprise Blue 的白底报告改造版：企业蓝、石墨灰、冷灰网格，适合技术与平台型业务。

```css
:root {
  --report-bg: #ffffff;
  --report-surface: #ffffff;
  --report-subtle: #f4f7fb;
  --report-subtle-2: #e8eef7;

  --text-primary: #161616;
  --text-secondary: #525252;
  --text-muted: #6f6f6f;
  --border-subtle: #e0e0e0;
  --border-strong: #c6c6c6;

  --accent-primary: #0f62fe;
  --accent-secondary: #4589ff;
  --accent-tertiary: #8a6d3b;
  --accent-soft: #edf5ff;
  --accent-strong: #002d9c;

  --semantic-positive: #198038;
  --semantic-negative: #da1e28;
  --semantic-warning: #b28600;
  --semantic-info: #0043ce;

  --chart-1: #0f62fe;
  --chart-2: #4589ff;
  --chart-3: #6f6f6f;
  --chart-4: #8a6d3b;
  --chart-5: #198038;
  --chart-6: #da1e28;
  --echarts-palette: #0f62fe, #4589ff, #6f6f6f, #8a6d3b, #198038, #da1e28;
}
```

## C. Corporate Neutral — 通用商务

灰白文档感，单一蓝色点缀。安全、克制、适合长时间阅读。

```css
:root {
  --report-bg: #ffffff;
  --report-surface: #ffffff;
  --report-subtle: #f8fafc;
  --report-subtle-2: #eef2f7;

  --text-primary: #1f2937;
  --text-secondary: #4b5563;
  --text-muted: #6b7280;
  --border-subtle: #e5e7eb;
  --border-strong: #d1d5db;

  --accent-primary: #2563eb;
  --accent-secondary: #60a5fa;
  --accent-tertiary: #a16207;
  --accent-soft: #eff6ff;
  --accent-strong: #1e40af;

  --semantic-positive: #059669;
  --semantic-negative: #dc2626;
  --semantic-warning: #d97706;
  --semantic-info: #2563eb;

  --chart-1: #2563eb;
  --chart-2: #64748b;
  --chart-3: #60a5fa;
  --chart-4: #a16207;
  --chart-5: #059669;
  --chart-6: #dc2626;
  --echarts-palette: #2563eb, #64748b, #60a5fa, #a16207, #059669, #dc2626;
}
```

## D. Financial Trust — 金融/订阅/收入模型

源自 Coinbase / Wise 的信任蓝逻辑：白底、金融蓝、深灰、绿色/红色只承担语义。

```css
:root {
  --report-bg: #ffffff;
  --report-surface: #ffffff;
  --report-subtle: #f6f8fb;
  --report-subtle-2: #eaf1fb;

  --text-primary: #111827;
  --text-secondary: #374151;
  --text-muted: #6b7280;
  --border-subtle: #dbe4f0;
  --border-strong: #c7d2df;

  --accent-primary: #0052cc;
  --accent-secondary: #2f80ed;
  --accent-tertiary: #9a6700;
  --accent-soft: #edf4ff;
  --accent-strong: #003a8c;

  --semantic-positive: #0f7a4f;
  --semantic-negative: #b42318;
  --semantic-warning: #b45309;
  --semantic-info: #0052cc;

  --chart-1: #0052cc;
  --chart-2: #2f80ed;
  --chart-3: #475569;
  --chart-4: #9a6700;
  --chart-5: #0f7a4f;
  --chart-6: #b42318;
  --echarts-palette: #0052cc, #2f80ed, #475569, #9a6700, #0f7a4f, #b42318;
}
```

## E. Boardroom Green — 增长/战略建议

深绿作为治理与增长信号，保持白底和灰色结构线，避免页面泛绿。

```css
:root {
  --report-bg: #ffffff;
  --report-surface: #ffffff;
  --report-subtle: #f8faf9;
  --report-subtle-2: #edf5ef;

  --text-primary: #111827;
  --text-secondary: #3f4b45;
  --text-muted: #6b7280;
  --border-subtle: #d8e3dd;
  --border-strong: #c4d4ca;

  --accent-primary: #166534;
  --accent-secondary: #15803d;
  --accent-tertiary: #a16207;
  --accent-soft: #eef7f0;
  --accent-strong: #14532d;

  --semantic-positive: #15803d;
  --semantic-negative: #b91c1c;
  --semantic-warning: #b45309;
  --semantic-info: #2563eb;

  --chart-1: #166534;
  --chart-2: #15803d;
  --chart-3: #64748b;
  --chart-4: #a16207;
  --chart-5: #2563eb;
  --chart-6: #b91c1c;
  --echarts-palette: #166534, #15803d, #64748b, #a16207, #2563eb, #b91c1c;
}
```

## F. Monochrome Executive — 极简董事会风格

黑灰为主，一种蓝色作为信息定位，红/绿只做风险与正向语义。

```css
:root {
  --report-bg: #ffffff;
  --report-surface: #ffffff;
  --report-subtle: #f7f7f7;
  --report-subtle-2: #eeeeee;

  --text-primary: #18181b;
  --text-secondary: #3f3f46;
  --text-muted: #71717a;
  --border-subtle: #e4e4e7;
  --border-strong: #d4d4d8;

  --accent-primary: #18181b;
  --accent-secondary: #3b82f6;
  --accent-tertiary: #8a6d3b;
  --accent-soft: #f3f4f6;
  --accent-strong: #09090b;

  --semantic-positive: #15803d;
  --semantic-negative: #b91c1c;
  --semantic-warning: #a16207;
  --semantic-info: #2563eb;

  --chart-1: #18181b;
  --chart-2: #52525b;
  --chart-3: #a1a1aa;
  --chart-4: #3b82f6;
  --chart-5: #15803d;
  --chart-6: #b91c1c;
  --echarts-palette: #18181b, #52525b, #a1a1aa, #3b82f6, #15803d, #b91c1c;
}
```

## 旧方案兼容

旧 `color_scheme` 会被组装器映射到新的正式报告方案：

| 旧值 | 新值 |
|------|------|
| `mckinsey-blue` | `consulting-navy` |
| `modern-slate` | `institutional-blue` |
| `warm-clay` | `corporate-neutral` |
| `forest-green` | `boardroom-green` |
| `minimal-light` | `monochrome-executive` |

## 变量说明

生成图表片段时，优先使用新变量：

| 变量 | 用途 |
|------|------|
| `--chart-1` 到 `--chart-6` | 图表系列色，ECharts/SVG/HTML 图形的主色来源 |
| `--accent-primary` | 标题竖线、关键边框、主强调 |
| `--accent-secondary` | 辅助强调、第二图表色 |
| `--accent-tertiary` | 少量深金/棕金点缀 |
| `--semantic-positive` | 正向/改善/增长 |
| `--semantic-negative` | 风险/下降/负面 |
| `--semantic-warning` | 警示/不确定性 |
| `--text-primary` / `--text-secondary` / `--text-muted` | 正文和注释文字 |
| `--border-subtle` / `--border-strong` | 表格、图表、组件边框 |

兼容旧片段时，组装器会把 `--color-primary`、`--color-positive`、`--color-negative` 等旧变量映射到上述正式报告 token。
