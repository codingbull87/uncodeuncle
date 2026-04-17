# Report Visual Systems — 正式报告视觉系统

> 这里不是网页主题。所有方案都保持白色底板，变化点是：图表色、标题点缀、表格/卡片处理、语义色与组件细节参数。

## 视觉系统一览

| 代号 | `color_scheme` | 名称 | 风格定位 | 适用场景 |
|------|----------------|------|----------|----------|
| **A** | `green` | Green | 麦肯锡系深绿主轴，咨询交付密度 | 战略研究、投资判断、咨询交付 |
| **B** | `warm` | Warm | 暖中性叙事风，正文阅读友好 | 长文研究、管理层叙事、结论解释 |
| **C** | `wine` | Wine | 酒红+炭黑，观点表达更鲜明 | 高层点评、品牌战略、竞争判断 |
| **D** | `black` | Black | 黑灰主轴，最克制的执行风 | 董事会摘要、财务页、文字密集页 |
| **E** | `blue` | Blue | 机构蓝+冷灰，系统化商务风 | 企业级/平台级/机构汇报 |

## 白底硬约束

```css
--report-bg: #ffffff;
--report-surface: #ffffff;
--paper: #ffffff;
```

禁止把 `.page`、正文区、图表容器改成深色或高饱和底色。

## A. Green — McKinsey Green

```css
:root {
  --report-bg: #ffffff;
  --report-surface: #ffffff;
  --report-subtle: #f5f8f7;
  --report-subtle-2: #e8efec;

  --text-primary: #1a2020;
  --text-secondary: #3f4d4b;
  --text-muted: #6a7573;
  --border-subtle: #d8e1de;
  --border-strong: #c2d1cd;

  --accent-primary: #005b4f;
  --accent-secondary: #0f766e;
  --accent-tertiary: #8a6d3b;
  --accent-soft: #e8f2ef;
  --accent-strong: #00443b;

  --semantic-positive: #1f7a53;
  --semantic-negative: #b42318;
  --semantic-warning: #a16207;
  --semantic-info: #0f766e;

  --chart-1: #005b4f;
  --chart-2: #0f766e;
  --chart-3: #334155;
  --chart-4: #8a6d3b;
  --chart-5: #1f7a53;
  --chart-6: #b42318;
  --echarts-palette: #005b4f, #0f766e, #334155, #8a6d3b, #1f7a53, #b42318;

  --style-title-rule-width: 3px;
  --style-section-accent-width: 4px;
  --style-card-radius: 6px;
  --style-kpi-accent-width: 4px;
  --style-panel-top-accent-width: 3px;
  --style-header-fill: var(--report-subtle-2);
  --style-table-stripe-fill: #f8fbfa;
  --style-risk-high-bg: #fff2f0;
  --style-risk-mid-bg: #fff9ec;
  --style-risk-low-bg: #eef8f2;
  --style-risk-high-border: #efbeb8;
  --style-risk-mid-border: #e7d6ab;
  --style-risk-low-border: #b8dbc9;
}
```

## B. Warm — Editorial Warm

```css
:root {
  --report-bg: #ffffff;
  --report-surface: #ffffff;
  --report-subtle: #f8f6f1;
  --report-subtle-2: #f1eee6;

  --text-primary: #2f2d2a;
  --text-secondary: #5e5d59;
  --text-muted: #87867f;
  --border-subtle: #e6e1d7;
  --border-strong: #d7d0c2;

  --accent-primary: #c96442;
  --accent-secondary: #d97757;
  --accent-tertiary: #6f7c5e;
  --accent-soft: #f8ede8;
  --accent-strong: #a24f34;

  --semantic-positive: #3f6d4e;
  --semantic-negative: #b53333;
  --semantic-warning: #9c6f2f;
  --semantic-info: #88513f;

  --chart-1: #c96442;
  --chart-2: #d97757;
  --chart-3: #5e5d59;
  --chart-4: #6f7c5e;
  --chart-5: #3f6d4e;
  --chart-6: #b53333;
  --echarts-palette: #c96442, #d97757, #5e5d59, #6f7c5e, #3f6d4e, #b53333;

  --style-title-rule-width: 3px;
  --style-section-accent-width: 4px;
  --style-card-radius: 8px;
  --style-kpi-accent-width: 4px;
  --style-panel-top-accent-width: 3px;
  --style-header-fill: var(--report-subtle-2);
  --style-table-stripe-fill: #fbf9f4;
  --style-risk-high-bg: #fff3f1;
  --style-risk-mid-bg: #fff8ee;
  --style-risk-low-bg: #f1f8f1;
  --style-risk-high-border: #efc3bb;
  --style-risk-mid-border: #e8d4ad;
  --style-risk-low-border: #c1d8c6;
}
```

## C. Wine — Burgundy Strategy

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
  --accent-secondary: #a63257;
  --accent-tertiary: #8d6b2f;
  --accent-soft: #f6ecef;
  --accent-strong: #5a122a;

  --semantic-positive: #2a6a50;
  --semantic-negative: #a12433;
  --semantic-warning: #9a6b1b;
  --semantic-info: #8f2f4f;

  --chart-1: #7a1f3d;
  --chart-2: #a63257;
  --chart-3: #5a122a;
  --chart-4: #8d6b2f;
  --chart-5: #2a6a50;
  --chart-6: #a12433;
  --echarts-palette: #7a1f3d, #a63257, #5a122a, #8d6b2f, #2a6a50, #a12433;

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

## D. Black — Executive Mono

```css
:root {
  --report-bg: #ffffff;
  --report-surface: #ffffff;
  --report-subtle: #f7f7f7;
  --report-subtle-2: #ededed;

  --text-primary: #111111;
  --text-secondary: #2f3136;
  --text-muted: #707072;
  --border-subtle: #d6d9de;
  --border-strong: #c6cacf;

  --accent-primary: #111111;
  --accent-secondary: #1151ff;
  --accent-tertiary: #4b4b4d;
  --accent-soft: #f1f1f1;
  --accent-strong: #000000;

  --semantic-positive: #007d48;
  --semantic-negative: #d30005;
  --semantic-warning: #9f5f00;
  --semantic-info: #1151ff;

  --chart-1: #111111;
  --chart-2: #4b4b4d;
  --chart-3: #9e9ea0;
  --chart-4: #1151ff;
  --chart-5: #007d48;
  --chart-6: #d30005;
  --echarts-palette: #111111, #4b4b4d, #9e9ea0, #1151ff, #007d48, #d30005;

  --style-title-rule-width: 4px;
  --style-section-accent-width: 5px;
  --style-card-radius: 4px;
  --style-kpi-accent-width: 5px;
  --style-panel-top-accent-width: 4px;
  --style-header-fill: var(--report-subtle-2);
  --style-table-stripe-fill: #fafafa;
  --style-risk-high-bg: #fff1f1;
  --style-risk-mid-bg: #fff8ea;
  --style-risk-low-bg: #eef8f2;
  --style-risk-high-border: #eababb;
  --style-risk-mid-border: #ead8b6;
  --style-risk-low-border: #bddbc9;
}
```

## E. Blue — Institutional Grid

```css
:root {
  --report-bg: #ffffff;
  --report-surface: #ffffff;
  --report-subtle: #f4f4f4;
  --report-subtle-2: #e9ecef;

  --text-primary: #161616;
  --text-secondary: #3f4b5a;
  --text-muted: #6f6f6f;
  --border-subtle: #d4dce5;
  --border-strong: #c0c9d5;

  --accent-primary: #0f62fe;
  --accent-secondary: #0043ce;
  --accent-tertiary: #8a6d3b;
  --accent-soft: #edf5ff;
  --accent-strong: #002d9c;

  --semantic-positive: #198038;
  --semantic-negative: #da1e28;
  --semantic-warning: #b28600;
  --semantic-info: #0043ce;

  --chart-1: #0f62fe;
  --chart-2: #0043ce;
  --chart-3: #6f6f6f;
  --chart-4: #8a6d3b;
  --chart-5: #198038;
  --chart-6: #da1e28;
  --echarts-palette: #0f62fe, #0043ce, #6f6f6f, #8a6d3b, #198038, #da1e28;

  --style-title-rule-width: 2px;
  --style-section-accent-width: 3px;
  --style-card-radius: 4px;
  --style-kpi-accent-width: 3px;
  --style-panel-top-accent-width: 2px;
  --style-header-fill: var(--report-subtle-2);
  --style-table-stripe-fill: #f9fbfd;
  --style-risk-high-bg: #fff3f4;
  --style-risk-mid-bg: #fff9ef;
  --style-risk-low-bg: #eff8f1;
  --style-risk-high-border: #f2bcc0;
  --style-risk-mid-border: #e9d6ab;
  --style-risk-low-border: #bedbc8;
}
```

## 旧方案兼容

| 旧值 | 新值 |
|------|------|
| `consulting-classic` | `green` |
| `institutional-carbon` | `blue` |
| `banker-monochrome` | `black` |
| `financial-blue` | `blue` |
| `burgundy-editorial` | `wine` |
| `consulting-navy` | `green` |
| `institutional-blue` | `blue` |
| `corporate-neutral` | `blue` |
| `financial-trust` | `blue` |
| `boardroom-green` | `green` |
| `monochrome-executive` | `black` |
| `mckinsey-blue` | `green` |
| `modern-slate` | `blue` |
| `warm-clay` | `warm` |
| `forest-green` | `green` |
| `minimal-light` | `black` |

## 变量说明

| 变量组 | 用途 |
|--------|------|
| `--chart-*` | 图表序列色 |
| `--accent-*` | 标题/边框/强调点缀 |
| `--semantic-*` | 风险、正向、警示 |
| `--style-*` | 组件处理参数（线宽、圆角、表头、风险格样式） |
