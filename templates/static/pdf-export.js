(function () {
  var chartHeightCache = new Map();
  var blockShrinkCache = new Map();
  var isPdfExportMode = false;

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

  function applyAdaptivePrintCompaction() {
    resetCompactPrint();
    var page = document.querySelector('.page');
    if (!page) return;

    var pageHeight = getPrintablePageHeightPx();

    function compactBlock(block, chartShrinkPx, aggressive) {
      var currentShrink = blockShrinkCache.get(block) || 0;
      if (chartShrinkPx <= currentShrink) return false;
      blockShrinkCache.set(block, chartShrinkPx);
      block.classList.add('compact-print');
      if (aggressive || chartShrinkPx >= 56) {
        block.classList.add('page-fit-compact');
      }
      block.querySelectorAll('[id^="chart-C"]').forEach(function (chartDom) {
        if (!chartHeightCache.has(chartDom)) {
          var inlineHeight = chartDom.style.height || '';
          var computedHeight = window.getComputedStyle(chartDom).height || '';
          chartHeightCache.set(chartDom, inlineHeight || computedHeight);
        }
        var originHeight = chartHeightCache.get(chartDom) || '';
        var parsed = parseInt(originHeight, 10);
        if (!isNaN(parsed) && parsed > 120) {
          chartDom.style.height = Math.max(parsed - chartShrinkPx, 120) + 'px';
        }
      });
      return true;
    }

    function runPass() {
      var changed = false;
      var targets = Array.prototype.slice.call(document.querySelectorAll('.visual-block, .visual-row'));
      var geometry = targets.map(function (block) {
        return {
          block: block,
          top: elementTopWithinPage(block, page),
          height: Math.ceil(block.getBoundingClientRect().height),
          hasChart: !!block.querySelector('[id^="chart-C"]'),
        };
      });

      geometry.forEach(function (item, index) {
        if (!item.height || !item.hasChart) return;
        var used = item.top % pageHeight;
        var remain = pageHeight - used;
        var overflow = item.height - remain;

        // Case A: block almost fits current page, pull it upward by targeted shrink.
        if (overflow > 0 && remain > 120 && overflow <= 340) {
          var need = Math.min(160, Math.max(26, overflow + 14));
          if (compactBlock(item.block, need, need >= 56)) changed = true;
        }

        // Case B: block starts near next page top, previous page has excessive blank.
        var startsNearTop = used <= 145;
        if (!startsNearTop) return;
        var prevBlank = pageHeight - used;
        if (prevBlank < 260) return;
        if (item.height < 200) return;
        var desiredBlank = 210;
        var needBackfill = Math.min(180, Math.max(36, Math.round((prevBlank - desiredBlank) * 0.9)));
        // When the block is already close to fitting previous page, give a little more push.
        var fitNeed = item.height - (prevBlank - 16);
        if (fitNeed > 0) {
          needBackfill = Math.min(180, Math.max(needBackfill, fitNeed + 18));
        }
        if (compactBlock(item.block, needBackfill, true)) changed = true;
      });
      return changed;
    }

    for (var pass = 0; pass < 6; pass += 1) {
      var changed = runPass();
      resizeCharts();
      if (!changed) break;
    }
  }

  function markChartsReady() {
    document.documentElement.classList.add('charts-ready');
  }

  window.addEventListener('load', function () {
    resizeCharts();
    window.setTimeout(function () {
      resizeCharts();
      if (isPdfExportMode) {
        applyAdaptivePrintCompaction();
        resizeCharts();
        window.setTimeout(function () {
          applyAdaptivePrintCompaction();
          resizeCharts();
        }, 220);
      }
      markChartsReady();
    }, 300);
  });

  window.addEventListener('beforeprint', function () {
    applyAdaptivePrintCompaction();
    resizeCharts();
    window.setTimeout(resizeCharts, 0);
  });
  window.addEventListener('afterprint', resetCompactPrint);
  window.addEventListener('resize', resizeCharts);

  var btn = document.getElementById('pdf-export-btn');
  if (!btn) return;

  btn.addEventListener('click', function () {
    applyAdaptivePrintCompaction();
    resizeCharts();
    window.setTimeout(function () {
      window.print();
    }, 150);
  });
})();
