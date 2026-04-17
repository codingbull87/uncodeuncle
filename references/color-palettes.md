# Report Visual Systems — 正式报告视觉系统

> 这里不是网页主题。所有方案都保持白色底板，变化点是：图表色、标题点缀、表格/卡片处理、语义色与组件细节参数。

## 视觉系统一览

| 代号 | `color_scheme` | 名称 | 风格定位 | 适用场景 |
|------|----------------|------|----------|----------|
| **A** | `consulting-classic` | Consulting Classic | 深蓝+深金，咨询交付密度 | 战略研究、投资判断、咨询交付 |
| **B** | `institutional-carbon` | Institutional Carbon | 企业蓝+冷灰，系统化 | 科技平台、机构汇报、管理层材料 |
| **C** | `banker-monochrome` | Banker Monochrome | 黑灰+少量蓝，投行 memo | 董事会摘要、文字密集、财务页 |
| **D** | `financial-blue` | Financial Blue | 信任蓝+语义红绿，金融分析 | 订阅、ARPU、收入模型、估值框架 |
| **E** | `burgundy-editorial` | Burgundy Editorial | 酒红+炭黑+暗金，编辑化正式风 | 消费品牌、战略评论、高层叙事页 |

## 白底硬约束

```css
--report-bg: #ffffff;
--report-surface: #ffffff;
--paper: #ffffff;
```

禁止把 `.page`、正文区、图表容器改成深色或高饱和底色。

## A. Consulting Classic — 深蓝咨询风

```css
:root {
  --report-bg: #ffffff;
  --report-surface: #ffffff;
  --report-subtle: #f7f8fa;
  --report-subtle-2: #eef2f7;

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

  --style-title-rule-width: 3px;
  --style-section-accent-width: 4px;
  --style-card-radius: 6px;
  --style-kpi-accent-width: 4px;
  --style-panel-top-accent-width: 3px;
  --style-header-fill: var(--report-subtle-2);
  --style-table-stripe-fill: var(--report-subtle);
  --style-risk-high-bg: #fff1ef;
  --style-risk-mid-bg: #fff8e8;
  --style-risk-low-bg: #eefaf4;
  --style-risk-high-border: #f4b4aa;
  --style-risk-mid-border: #f7d28a;
  --style-risk-low-border: #a8dbc6;
}
```

## B. Institutional Carbon — 企业系统风

```css
:root {
  --report-bg: #ffffff;
  --report-surface: #ffffff;
  --report-subtle: #f4f7fb;
  --report-subtle-2: #e9eff8;

  --text-primary: #161616;
  --text-secondary: #3f4b5a;
  --text-muted: #6b7280;
  --border-subtle: #dce3ec;
  --border-strong: #c8d3e1;

  --accent-primary: #0f62fe;
  --accent-secondary: #3b82f6;
  --accent-tertiary: #8a6d3b;
  --accent-soft: #edf5ff;
  --accent-strong: #003a8c;

  --semantic-positive: #198038;
  --semantic-negative: #da1e28;
  --semantic-warning: #b28600;
  --semantic-info: #0043ce;

  --chart-1: #0f62fe;
  --chart-2: #4589ff;
  --chart-3: #6b7280;
  --chart-4: #8a6d3b;
  --chart-5: #198038;
  --chart-6: #da1e28;
  --echarts-palette: #0f62fe, #4589ff, #6b7280, #8a6d3b, #198038, #da1e28;

  --style-title-rule-width: 2px;
  --style-section-accent-width: 3px;
  --style-card-radius: 8px;
  --style-kpi-accent-width: 3px;
  --style-panel-top-accent-width: 2px;
  --style-header-fill: var(--report-subtle-2);
  --style-table-stripe-fill: #f9fbff;
  --style-risk-high-bg: #fff3f4;
  --style-risk-mid-bg: #fff9ef;
  --style-risk-low-bg: #eef8f1;
  --style-risk-high-border: #f2bcc0;
  --style-risk-mid-border: #e9d6ab;
  --style-risk-low-border: #bedbc8;
}
```

## C. Banker Monochrome — 投行黑灰风

```css
:root {
  --report-bg: #ffffff;
  --report-surface: #ffffff;
  --report-subtle: #f6f6f7;
  --report-subtle-2: #ececee;

  --text-primary: #111111;
  --text-secondary: #2f3136;
  --text-muted: #61656f;
  --border-subtle: #d8dbe1;
  --border-strong: #c5c8cf;

  --accent-primary: #18181b;
  --accent-secondary: #3b82f6;
  --accent-tertiary: #7b674a;
  --accent-soft: #f1f2f4;
  --accent-strong: #09090b;

  --semantic-positive: #1f6a43;
  --semantic-negative: #9f1f24;
  --semantic-warning: #8a6f1d;
  --semantic-info: #2f5fb3;

  --chart-1: #18181b;
  --chart-2: #52525b;
  --chart-3: #8e8e97;
  --chart-4: #3b82f6;
  --chart-5: #1f6a43;
  --chart-6: #9f1f24;
  --echarts-palette: #18181b, #52525b, #8e8e97, #3b82f6, #1f6a43, #9f1f24;

  --style-title-rule-width: 2px;
  --style-section-accent-width: 3px;
  --style-card-radius: 4px;
  --style-kpi-accent-width: 3px;
  --style-panel-top-accent-width: 2px;
  --style-header-fill: var(--report-subtle-2);
  --style-table-stripe-fill: #f8f8f9;
  --style-risk-high-bg: #faf2f2;
  --style-risk-mid-bg: #faf8f1;
  --style-risk-low-bg: #f0f5f2;
  --style-risk-high-border: #dfc0c1;
  --style-risk-mid-border: #dfd1af;
  --style-risk-low-border: #c3d6c9;
}
```

## D. Financial Blue — 金融信任风

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

  --style-title-rule-width: 3px;
  --style-section-accent-width: 4px;
  --style-card-radius: 6px;
  --style-kpi-accent-width: 4px;
  --style-panel-top-accent-width: 3px;
  --style-header-fill: var(--report-subtle-2);
  --style-table-stripe-fill: #f8fbff;
  --style-risk-high-bg: #fff2f0;
  --style-risk-mid-bg: #fff7e7;
  --style-risk-low-bg: #eef8f2;
  --style-risk-high-border: #efb8b0;
  --style-risk-mid-border: #e9cf96;
  --style-risk-low-border: #b7dbc9;
}
```

## E. Burgundy Editorial — 酒红编辑风

```css
:root {
  --report-bg: #ffffff;
  --report-surface: #ffffff;
  --report-subtle: #f9f6f7;
  --report-subtle-2: #f1eaec;

  --text-primary: #1d1b1c;
  --text-secondary: #4b4346;
  --text-muted: #756a6f;
  --border-subtle: #e6dde0;
  --border-strong: #d7c8cd;

  --accent-primary: #7a1f3d;
  --accent-secondary: #b23a5f;
  --accent-tertiary: #8d6b2f;
  --accent-soft: #f6ecef;
  --accent-strong: #5a122a;

  --semantic-positive: #2a6a50;
  --semantic-negative: #a12433;
  --semantic-warning: #9a6b1b;
  --semantic-info: #8f2f4f;

  --chart-1: #7a1f3d;
  --chart-2: #b23a5f;
  --chart-3: #756a6f;
  --chart-4: #8d6b2f;
  --chart-5: #2a6a50;
  --chart-6: #a12433;
  --echarts-palette: #7a1f3d, #b23a5f, #756a6f, #8d6b2f, #2a6a50, #a12433;

  --style-title-rule-width: 3px;
  --style-section-accent-width: 4px;
  --style-card-radius: 6px;
  --style-kpi-accent-width: 4px;
  --style-panel-top-accent-width: 3px;
  --style-header-fill: var(--report-subtle-2);
  --style-table-stripe-fill: #fbf8f9;
  --style-risk-high-bg: #fff1f3;
  --style-risk-mid-bg: #fff7eb;
  --style-risk-low-bg: #edf7f2;
  --style-risk-high-border: #efbcc9;
  --style-risk-mid-border: #e8d3a8;
  --style-risk-low-border: #b8d8c8;
}
```

## 旧方案兼容

| 旧值 | 新值 |
|------|------|
| `consulting-navy` | `consulting-classic` |
| `institutional-blue` | `institutional-carbon` |
| `corporate-neutral` | `financial-blue` |
| `financial-trust` | `financial-blue` |
| `boardroom-green` | `financial-blue` |
| `monochrome-executive` | `banker-monochrome` |
| `mckinsey-blue` | `consulting-classic` |
| `modern-slate` | `institutional-carbon` |
| `warm-clay` | `burgundy-editorial` |
| `forest-green` | `financial-blue` |
| `minimal-light` | `banker-monochrome` |

## 变量说明

| 变量组 | 用途 |
|--------|------|
| `--chart-*` | 图表序列色 |
| `--accent-*` | 标题/边框/强调点缀 |
| `--semantic-*` | 风险、正向、警示 |
| `--style-*` | 组件处理参数（线宽、圆角、表头、风险格样式） |
