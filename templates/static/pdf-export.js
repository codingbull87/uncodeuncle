(function () {
  var chartHeightCache = new Map();
  var blockShrinkCache = new Map();
  var isPdfExportMode = false;
  var chartResizeObserver = null;
  var pendingResizeTimer = 0;

  try {
    isPdfExportMode = new URLSearchParams(window.location.search).get('pdf') === '1';
  } catch (e) {
    isPdfExportMode = false;
  }
  if (isPdfExportMode) {
    document.documentElement.classList.add('pdf-export-mode');
  }

  function resizeCharts() {
    if (!window.echarts) return;
    document.querySelectorAll('[id^="chart-C"]').forEach(function (dom) {
      var instance = echarts.getInstanceByDom(dom);
      if (instance) instance.resize();
    });
  }

  function scheduleChartResize(delay) {
    if (pendingResizeTimer) {
      window.clearTimeout(pendingResizeTimer);
    }
    pendingResizeTimer = window.setTimeout(function () {
      pendingResizeTimer = 0;
      resizeCharts();
    }, delay || 0);
  }

  function bindChartObservers() {
    if (!window.ResizeObserver || chartResizeObserver) return;
    chartResizeObserver = new ResizeObserver(function () {
      scheduleChartResize(36);
    });
    document.querySelectorAll('[id^="chart-C"]').forEach(function (dom) {
      if (dom.parentElement) chartResizeObserver.observe(dom.parentElement);
      if (dom.parentElement && dom.parentElement.parentElement) {
        chartResizeObserver.observe(dom.parentElement.parentElement);
      }
    });
    document.querySelectorAll('.visual-row, .visual-block:not(.visual-block-nested)').forEach(function (node) {
      chartResizeObserver.observe(node);
    });
  }

  function getPrintablePageHeightPx() {
    var mmToPx = 96 / 25.4;
    var pageMm = 297 - 16 - 18; // A4 height - top/bottom margins from @page
    return Math.round(pageMm * mmToPx);
  }

  function elementTopWithinPage(el, page) {
    var top = 0;
    var node = el;
    while (node && node !== page) {
      top += node.offsetTop || 0;
      node = node.offsetParent;
    }
    return top;
  }

  function resetCompactPrint() {
    document.querySelectorAll('h2.chapter-page-break').forEach(function (el) {
      el.classList.remove('chapter-page-break');
    });
    document.querySelectorAll('.compact-print, .page-fit-compact').forEach(function (el) {
      el.classList.remove('compact-print');
      el.classList.remove('page-fit-compact');
    });
    chartHeightCache.forEach(function (originHeight, dom) {
      dom.style.height = originHeight;
    });
    chartHeightCache.clear();
    blockShrinkCache.clear();
  }

  function applyChapterBreaks(pageHeight) {
    var page = document.querySelector('.page');
    if (!page) return;
    function nextContentSibling(heading) {
      var node = heading.nextElementSibling;
      while (node) {
        if (node.matches && node.matches('h1,h2,h3,.visual-row,.visual-block:not(.visual-block-nested),table,blockquote,p,ul,ol')) {
          return node;
        }
        node = node.nextElementSibling;
      }
      return null;
    }
    function bundleNeedPx(heading) {
      var need = Math.ceil(heading.getBoundingClientRect().height || 0) + 36;
      var count = 0;
      var node = nextContentSibling(heading);
      while (node && count < 2) {
        var rect = node.getBoundingClientRect();
        if (rect.height) {
          need += Math.min(Math.ceil(rect.height), count === 0 ? 210 : 140);
          count += 1;
        }
        if (node.matches && node.matches('h2')) break;
        node = node.nextElementSibling;
      }
      return Math.max(150, Math.min(need, 340));
    }
    var headings = Array.prototype.slice.call(page.querySelectorAll('h2'));
    headings.forEach(function (heading, index) {
      if (index === 0) return;
      var used = elementTopWithinPage(heading, page) % pageHeight;
      var remain = pageHeight - used;
      var need = bundleNeedPx(heading);
      // Be conservative: only force chapter break when heading is very close
      // to page bottom and remaining space is clearly insufficient.
      if (used > pageHeight * 0.82 && remain < Math.min(need, Math.round(pageHeight * 0.20))) {
        heading.classList.add('chapter-page-break');
      }
    });
  }

  function applyAdaptivePrintCompaction() {
    resetCompactPrint();
  }

  function markChartsReady() {
    document.documentElement.classList.add('charts-ready');
  }

  window.addEventListener('load', function () {
    bindChartObservers();
    resizeCharts();
    window.requestAnimationFrame(resizeCharts);
    window.setTimeout(function () {
      resizeCharts();
      window.requestAnimationFrame(resizeCharts);
      if (isPdfExportMode) {
        applyChapterBreaks(getPrintablePageHeightPx());
      }
      markChartsReady();
    }, 300);
    window.setTimeout(resizeCharts, 900);
    window.setTimeout(resizeCharts, 1600);
  });

  window.addEventListener('beforeprint', function () {
    applyChapterBreaks(getPrintablePageHeightPx());
    resizeCharts();
    window.setTimeout(resizeCharts, 0);
  });
  window.addEventListener('afterprint', resetCompactPrint);
  window.addEventListener('resize', function () {
    scheduleChartResize(24);
  });

  var btn = document.getElementById('pdf-export-btn');
  if (!btn) return;

  btn.addEventListener('click', function () {
    applyChapterBreaks(getPrintablePageHeightPx());
    resizeCharts();
    window.setTimeout(function () {
      window.print();
    }, 150);
  });
})();
