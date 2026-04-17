# libs/ 目录说明

此目录存放离线渲染依赖。当前主流程只需要 ECharts。

## 必需文件

```text
echarts.min.js
```

生成报告前复制到输出目录：

```bash
mkdir -p {report_dir}/libs
cp {skill_dir}/libs/echarts.min.js {report_dir}/libs/
```

## PDF 导出

PDF 不再依赖 `html2canvas` 或 `jsPDF`。最终 PDF 由 `scripts/export_pdf.py` 调用 Chrome、Chromium 或 Edge 的打印引擎生成。

## 版本

当前打包文件为 ECharts 6.x。Generator 必须使用：

```javascript
echarts.init(dom, null, { renderer: 'svg' })
```

不要在新片段中使用 canvas renderer，除非用户明确放弃矢量 PDF 目标。
