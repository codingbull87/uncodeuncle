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
      if (used > pageHeight * 0.70 && remain < need) {
        heading.classList.add('chapter-page-break');
      }
    });
  }

  function applyAdaptivePrintCompaction() {
    resetCompactPrint();
    var page = document.querySelector('.page');
    if (!page) return;

    var pageHeight = getPrintablePageHeightPx();
    applyChapterBreaks(pageHeight);

    function canShrinkBlock(block) {
      return block.dataset.canShrink !== 'false';
    }

    function getMaxShrinkRatio(block) {
      var parsed = parseFloat(block.dataset.maxShrinkRatio || '');
      if (isNaN(parsed)) return 0.25;
      return Math.max(0, Math.min(parsed, 0.35));
    }

    function getChartOriginHeight(chartDom) {
      if (!chartHeightCache.has(chartDom)) {
        var inlineHeight = chartDom.style.height || '';
        var computedHeight = window.getComputedStyle(chartDom).height || '';
        chartHeightCache.set(chartDom, inlineHeight || computedHeight);
      }
      return parseInt(chartHeightCache.get(chartDom) || '', 10);
    }

    function getBlockShrinkPotential(block) {
      if (!canShrinkBlock(block)) return 0;
      var ratio = getMaxShrinkRatio(block);
      var potential = 0;
      block.querySelectorAll('[id^="chart-C"]').forEach(function (chartDom) {
        var parsed = getChartOriginHeight(chartDom);
        if (!isNaN(parsed) && parsed > 120) {
          potential += Math.max(0, Math.min(parsed * ratio, parsed - 120));
        }
      });
      return Math.floor(potential);
    }

    function compactBlock(block, chartShrinkPx, aggressive) {
      if (!canShrinkBlock(block)) return false;
      var currentShrink = blockShrinkCache.get(block) || 0;
      if (chartShrinkPx <= currentShrink) return false;
      blockShrinkCache.set(block, chartShrinkPx);
      block.classList.add('compact-print');
      if (aggressive || chartShrinkPx >= 56) {
        block.classList.add('page-fit-compact');
      }
      var shrinkRatio = getMaxShrinkRatio(block);
      block.querySelectorAll('[id^="chart-C"]').forEach(function (chartDom) {
        var parsed = getChartOriginHeight(chartDom);
        if (!isNaN(parsed) && parsed > 120) {
          var cap = Math.floor(parsed * shrinkRatio);
          var effectiveShrink = Math.min(chartShrinkPx, cap);
          chartDom.style.height = Math.max(parsed - effectiveShrink, 120) + 'px';
        }
      });
      return true;
    }

    function runPass() {
      var changed = false;
      var targets = Array.prototype.slice.call(document.querySelectorAll('.visual-row, .visual-block:not(.visual-block-nested)'));
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
        var shrinkPotential = getBlockShrinkPotential(item.block);
        if (shrinkPotential <= 0) return;

        // Case A: block almost fits current page, pull it upward by targeted shrink.
        if (overflow > 0 && remain > 140 && overflow <= 300 && shrinkPotential >= overflow) {
          var need = Math.min(150, Math.max(24, overflow + 12));
          if (compactBlock(item.block, need, need >= 56)) changed = true;
        }

        // Case B: block starts near next page top, previous page has excessive blank.
        var startsNearTop = used <= 145;
        if (!startsNearTop) return;
        var prevBlank = pageHeight - used;
        if (prevBlank < Math.round(pageHeight * 0.3)) return;
        if (item.height < 200) return;
        var desiredBlank = Math.round(pageHeight * 0.18);
        var fitNeed = item.height - (prevBlank - 16);
        if (fitNeed > shrinkPotential) return;
        var needBackfill = Math.min(150, Math.max(28, Math.round((prevBlank - desiredBlank) * 0.75)));
        if (fitNeed > 0) needBackfill = Math.min(150, Math.max(needBackfill, fitNeed + 12));
        if (compactBlock(item.block, needBackfill, true)) changed = true;
      });
      return changed;
    }

    for (var pass = 0; pass < 4; pass += 1) {
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
