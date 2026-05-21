const CF = {
  TIMEZONE: 'Europe/Sarajevo',

  charts: {},
  catalog: null,
  selection: { sales: null, products: null, inventory: null },
  pickerTarget: null,

  resetPendingMode: null,
  platformStatus: null,

  init() {
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        CF.closeSidebar();
        const deleteImport = document.getElementById('delete-import-modal');
        if (deleteImport?.style.display === 'flex') CF.closeDeleteImportModal();
        else {
          if (document.getElementById('clear-datasets-modal')?.style.display === 'flex') CF.closeClearDatasetsModal();
          if (document.getElementById('reset-analysis-modal')?.style.display === 'flex') CF.closeResetAnalysisModal();
          else {
            const picker = document.getElementById('picker-modal');
            if (picker?.style.display === 'flex') CF.closePickerModal();
            else CF.closeAnalysisModal();
          }
        }
      }
    });
    CF.loadActiveDatasetsBar();
    CF.refreshPlatformUI();
    CF.syncImportsOnLoad();
    const path = location.pathname;
    const loaders = {
      '/': 'loadDashboard',
      '/products': 'loadProducts',
      '/inventory': 'loadInventory',
      '/profit': 'loadProfit',
      '/alerts': 'loadAlerts',
      '/imports': 'initImports',
      '/reports': 'loadReports',
    };
    const fn = loaders[path];
    if (fn && fn !== 'initImports') CF[fn]();
    else if (fn === 'initImports') CF.initImports();
  },

  toggleSidebar() {
    document.getElementById('sidebar')?.classList.toggle('open');
    document.getElementById('sidebar-overlay')?.classList.toggle('visible');
  },

  closeSidebar() {
    document.getElementById('sidebar')?.classList.remove('open');
    document.getElementById('sidebar-overlay')?.classList.remove('visible');
  },

  async fetchJSON(url, options = {}) {
    const res = await fetch(url, options);
    const text = await res.text();
    let data = null;
    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        data = { message: text, raw: text };
      }
    }
    if (!res.ok) {
      const err = new Error(data?.message || data?.detail || text || `HTTP ${res.status}`);
      err.status = res.status;
      err.payload = data;
      throw err;
    }
    return data;
  },

  parseApiError(err) {
    const p = err.payload || {};
    const lines = [];
    if (p.message) lines.push(p.message);
    if (typeof p.detail === 'string') lines.push(p.detail);
    if (typeof p.detail === 'object' && p.detail?.message) lines.push(p.detail.message);
    if (p.validation?.warnings?.length) {
      lines.push('Validation: ' + p.validation.warnings.join('; '));
    }
    if (p.validation?.missing_columns) {
      Object.entries(p.validation.missing_columns).forEach(([ds, cols]) => {
        lines.push(`Missing in ${ds}: ${cols.join(', ')}`);
      });
    }
    if (p.errors?.length) {
      p.errors.forEach((e) => lines.push(`[${e.stage}] ${e.error_type}: ${e.message}`));
    }
    if (p.dataset_info?.row_counts) {
      const c = p.dataset_info.row_counts;
      lines.push(`DB rows — products: ${c.products}, sales: ${c.sales}, inventory: ${c.inventory}`);
    }
  if (p.traceback) lines.push(p.traceback.split('\n').slice(-4).join('\n'));
    return lines.filter(Boolean).join('\n') || err.message || 'Unknown error';
  },

  showAnalysisError(err) {
    const detail = CF.parseApiError(err);
    CF.showErrorPanel('Analysis failed', detail, err.payload);
    CF.toast(detail.split('\n')[0] || 'Analysis failed', 'error', 8000);
  },

  showErrorPanel(title, detail, payload = {}) {
    let panel = document.getElementById('analysis-error-panel');
    if (!panel) {
      panel = document.createElement('div');
      panel.id = 'analysis-error-panel';
      panel.className = 'analysis-error-panel';
      document.body.appendChild(panel);
    }
    const stages = (payload.stages || [])
      .map((s) => {
        const icon = s.status === 'completed' ? '✓' : s.status === 'failed' ? '✗' : '○';
        const cls = s.status === 'failed' ? 'stage-failed' : s.status === 'completed' ? 'stage-ok' : '';
        return `<li class="${cls}"><span>${icon}</span> ${s.label || s.name} — ${s.message || s.status}</li>`;
      })
      .join('');
    panel.innerHTML = `
      <div class="analysis-error-inner">
        <div class="analysis-error-header">
          <h3>${title}</h3>
          <button type="button" onclick="document.getElementById('analysis-error-panel').remove()" aria-label="Close">×</button>
        </div>
        <pre class="analysis-error-body">${CF.escapeHtml(detail)}</pre>
        ${stages ? `<ul class="analysis-stages">${stages}</ul>` : ''}
      </div>`;
    panel.style.display = 'block';
  },

  datasetTypeLabel(type) {
    return {
      sales: 'Sales Dataset',
      products: 'Products Dataset',
      inventory: 'Inventory Dataset',
      mixed: 'Mixed Dataset',
      unknown: 'Unknown',
    }[type] || type;
  },

  datasetTypeShortBadge(type) {
    const t = (type || 'unknown').toLowerCase();
    const labels = { sales: 'SALES', products: 'PRODUCTS', inventory: 'INVENTORY', mixed: 'MIXED', unknown: 'UNKNOWN' };
    return `<span class="badge-dataset-short badge-dataset-short-${t}">${labels[t] || 'UNKNOWN'}</span>`;
  },

  datasetTypeBadge(type, withCheck = false) {
    const t = (type || 'unknown').toLowerCase();
    const prefix = withCheck ? '✓ ' : '';
    return `<span class="badge-dataset badge-dataset-${t}">${prefix}${CF.datasetTypeLabel(t)}</span>`;
  },

  escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  },

  showAnalysisStages(stages) {
    if (!stages?.length) return;
    const failed = stages.filter((s) => s.status === 'failed');
    if (failed.length) {
      CF.toast(`${failed.length} stage(s) had issues — see details`, 'info', 5000);
    }
  },

  toast(message, type = 'info', duration = 4000) {
    const el = document.createElement('div');
    el.className = `toast toast-${type}`;
    el.textContent = message;
    document.getElementById('toast-container').appendChild(el);
    setTimeout(() => {
      el.style.opacity = '0';
      el.style.transform = 'translateX(100%)';
      setTimeout(() => el.remove(), 300);
    }, duration);
  },

  formatCurrency(n) {
    if (n === null || n === undefined) return 'Not available';
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);
  },

  formatPct(n) {
    if (n === null || n === undefined) return 'Not available';
    return `${Number(n).toFixed(1)}%`;
  },

  formatMetric(n, formatter = String) {
    if (n === null || n === undefined) return 'Not available';
    return formatter(n);
  },

  formatDateTime(iso, opts = {}) {
    if (!iso) return '—';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return '—';
    return new Intl.DateTimeFormat('en-GB', {
      timeZone: CF.TIMEZONE,
      dateStyle: opts.dateStyle || 'medium',
      timeStyle: opts.timeStyle || 'short',
    }).format(d);
  },

  formatDateShort(iso) {
    return CF.formatDateTime(iso, { dateStyle: 'medium', timeStyle: 'short' });
  },

  severityBadge(sev) {
    return `<span class="badge badge-${sev}">${sev}</span>`;
  },

  setLastUpdated() {
    const el = document.getElementById('last-updated');
    if (el) {
      el.textContent = `Updated ${CF.formatDateTime(new Date().toISOString(), { dateStyle: undefined, timeStyle: 'short' })}`;
      el.classList.remove('hidden');
    }
  },

  skeletonMetrics(count = 4) {
    return Array(count).fill(0).map((_, i) =>
      `<div class="skeleton skeleton-metric" style="animation-delay:${i * 0.08}s"></div>`
    ).join('');
  },

  skeletonChart() {
    return '<div class="skeleton skeleton-chart"></div>';
  },

  skeletonList(n = 5) {
    return Array(n).fill(0).map(() =>
      '<div class="skeleton skeleton-line" style="width:100%"></div>'
    ).join('');
  },

  showSkeleton(id, type = 'metrics', count = 4) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.add('content-loading');
    if (type === 'metrics') el.innerHTML = CF.skeletonMetrics(count);
    else if (type === 'chart') el.innerHTML = CF.skeletonChart();
    else if (type === 'list') el.innerHTML = CF.skeletonList(count);
  },

  reveal(el) {
    if (!el) return;
    el.classList.remove('content-loading');
    el.classList.add('content-loaded');
  },

  metricCard(label, value, sub = null, opts = {}) {
    const { accent = false, valueClass = '', trend = null } = opts;
    const trendHtml = trend
      ? `<span class="metric-trend metric-trend-${trend.type}">${trend.text}</span>`
      : '';
    return `<div class="metric-card ${accent ? 'metric-card-accent' : ''}" style="animation-delay:${opts.delay || 0}s">
      <p class="metric-label">${label}</p>
      <p class="metric-value mono ${valueClass}">${value}</p>
      ${sub ? `<p class="metric-sub">${sub}</p>` : ''}
      ${trendHtml}
    </div>`;
  },

  listRow(title, meta, value, valueClass = '') {
    return `<div class="list-row">
      <div><p class="list-row-title">${title}</p>${meta ? `<p class="list-row-meta">${meta}</p>` : ''}</div>
      <div class="list-row-value ${valueClass}">${value}</div>
    </div>`;
  },

  chartDefaults() {
    Chart.defaults.color = '#64748b';
    Chart.defaults.borderColor = 'rgba(255,255,255,0.04)';
    Chart.defaults.font.family = "'Inter', system-ui, sans-serif";
  },

  chartOptions(extra = {}) {
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 800, easing: 'easeOutCubic' },
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(14, 16, 22, 0.95)',
          titleColor: '#f1f5f9',
          bodyColor: '#94a3b8',
          borderColor: 'rgba(255,255,255,0.08)',
          borderWidth: 1,
          padding: 12,
          cornerRadius: 8,
          titleFont: { size: 12, weight: '600' },
          bodyFont: { size: 12 },
          displayColors: true,
          boxPadding: 4,
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: '#64748b', maxTicksLimit: 7, font: { size: 11 } },
          border: { display: false },
        },
        y: {
          grid: { color: 'rgba(255,255,255,0.04)', drawBorder: false },
          ticks: {
            color: '#64748b',
            font: { size: 11 },
            callback: (v) => (v >= 1000 ? `$${(v / 1000).toFixed(0)}k` : `$${v}`),
          },
          border: { display: false },
        },
      },
      ...extra,
    };
  },

  datasetTypes: [
    { key: 'sales', label: 'Sales Dataset' },
    { key: 'products', label: 'Products Dataset' },
    { key: 'inventory', label: 'Inventory Dataset' },
  ],

  async openAnalysisModal() {
    const modal = document.getElementById('analysis-modal');
    if (!modal) return;
    modal.style.display = 'flex';
    modal.setAttribute('aria-hidden', 'false');

    const pickers = document.getElementById('dataset-pickers');
    if (pickers) pickers.innerHTML = '<div class="skeleton skeleton-metric" style="height:4.5rem;margin-bottom:0.75rem"></div>'.repeat(3);

    let catalog = { sales: [], products: [], inventory: [] };
    try {
      catalog = await CF.fetchJSON('/api/imports/catalog');
      CF.catalog = catalog;
    } catch (e) {
      CF.toast('Could not load import history: ' + (CF.parseApiError(e).split('\n')[0] || 'error'), 'error');
      CF.catalog = catalog;
    }

    let active = { has_selection: false };
    try {
      active = await CF.fetchJSON('/api/analytics/active-datasets');
    } catch { /* optional */ }

    CF.selection = { sales: null, products: null, inventory: null };
    const find = (list, id) => (list || []).find((i) => i.id === id);
    if (active.sales_import_id) CF.selection.sales = find(catalog.sales, active.sales_import_id) || active.sales;
    if (active.products_import_id) CF.selection.products = find(catalog.products, active.products_import_id) || active.products;
    if (active.inventory_import_id) CF.selection.inventory = find(catalog.inventory, active.inventory_import_id) || active.inventory;

    CF.renderDatasetPickers();
    CF.updateAnalysisValidation();
  },

  closeAnalysisModal() {
    CF.closePickerModal();
    const modal = document.getElementById('analysis-modal');
    if (!modal) return;
    modal.style.display = 'none';
    modal.setAttribute('aria-hidden', 'true');
  },

  renderDatasetPickers() {
    const container = document.getElementById('dataset-pickers');
    if (!container) return;
    container.innerHTML = CF.datasetTypes.map(({ key, label }) => {
      const selected = CF.selection[key];
      const count = (CF.catalog?.[key] || []).length;
      return `
      <div class="dataset-picker-row">
        <p class="dataset-picker-label">${label}</p>
        <div class="dataset-picker-value">${selected ? CF.renderSelectedChip(selected) : '<span class="dataset-unselected">No file selected</span>'}</div>
        <div class="dataset-picker-actions">
          <button type="button" class="btn-choose-dataset" onclick="CF.openPickerModal('${key}')">
            Choose from Import History
            <span class="btn-choose-meta">${count} file${count === 1 ? '' : 's'}</span>
          </button>
          ${selected ? `<button type="button" class="btn-clear-dataset" onclick="CF.clearDataset('${key}')" title="Clear selection">×</button>` : ''}
        </div>
      </div>`;
    }).join('');
  },

  renderSelectedChip(item) {
    const rows = item.success_count || item.row_count || 0;
    const dtype = (item.dataset_type || '').toLowerCase();
    return `<span class="dataset-selected-chip">${CF.datasetTypeBadge(dtype, true)}<span class="dataset-selected-name">${CF.escapeHtml(item.display_name || item.filename)}</span><span class="dataset-selected-meta">(${rows} rows)</span></span>`;
  },

  openPickerModal(typeKey) {
    CF.pickerTarget = typeKey;
    const items = CF.catalog?.[typeKey] || [];
    const labels = { sales: 'Sales', products: 'Products', inventory: 'Inventory' };
    document.getElementById('picker-modal-title').textContent = `Choose ${labels[typeKey]} Dataset`;
    document.getElementById('picker-modal-sub').textContent = `Only ${labels[typeKey].toLowerCase()} datasets detected from column headers`;
    const search = document.getElementById('picker-search');
    if (search) search.value = '';
    const modal = document.getElementById('picker-modal');
    modal.style.display = 'flex';
    modal.setAttribute('aria-hidden', 'false');
    CF.renderPickerList(items);
  },

  closePickerModal() {
    const modal = document.getElementById('picker-modal');
    if (!modal) return;
    modal.style.display = 'none';
    modal.setAttribute('aria-hidden', 'true');
    CF.pickerTarget = null;
  },

  renderPickerList(items) {
    const list = document.getElementById('picker-list');
    const empty = document.getElementById('picker-empty');
    if (!list) return;
    if (!items.length) {
      list.innerHTML = '';
      empty?.classList.remove('hidden');
      return;
    }
    empty?.classList.add('hidden');
    list.innerHTML = items.map((item) => {
      const rows = item.success_count || item.row_count || 0;
      const ts = item.started_at ? CF.formatDateShort(item.started_at) : '';
      const dtype = (item.dataset_type || 'unknown').toLowerCase();
      return `
      <button type="button" class="picker-item" data-search="${CF.escapeHtml(item.filename).toLowerCase()} ${dtype}" onclick="CF.selectDatasetById(${item.id})">
        <div class="picker-item-main"><span class="picker-filename">${CF.escapeHtml(item.display_name || item.filename)}</span>${CF.datasetTypeBadge(dtype)}</div>
        <p class="picker-meta">${CF.escapeHtml(item.subtitle || `${rows} rows • imported ${ts}`)}</p>
      </button>`;
    }).join('');
  },

  filterPickerList() {
    const q = (document.getElementById('picker-search')?.value || '').toLowerCase();
    document.querySelectorAll('.picker-item').forEach((el) => {
      el.style.display = (el.getAttribute('data-search') || '').includes(q) ? '' : 'none';
    });
  },

  selectDatasetById(id) {
    const key = CF.pickerTarget;
    if (!key) return;
    const item = (CF.catalog?.[key] || []).find((i) => i.id === id);
    if (!item) {
      CF.toast('Import not found', 'error');
      return;
    }
    CF.selection[key] = item;
    CF.closePickerModal();
    CF.renderDatasetPickers();
    CF.updateAnalysisValidation();
  },

  clearDataset(key) {
    CF.selection[key] = null;
    CF.renderDatasetPickers();
    CF.updateAnalysisValidation();
  },

  requiredDatasetTypes() {
    return CF.datasetTypes
      .map((d) => d.key)
      .filter((key) => (CF.catalog?.[key] || []).length > 0);
  },

  updateAnalysisValidation() {
    const required = CF.requiredDatasetTypes();
    const missing = required.filter((key) => !CF.selection[key]);
    const btn = document.getElementById('btn-confirm-analysis');
    const msg = document.getElementById('analysis-validation-msg');
    const labels = { sales: 'Sales', products: 'Products', inventory: 'Inventory' };

    if (btn) btn.disabled = missing.length > 0;

    if (msg) {
      if (!required.length) {
        msg.textContent = 'No imported datasets yet. Upload files on Import History first.';
        msg.classList.remove('hidden');
      } else if (missing.length) {
        msg.textContent = `Select ${missing.map((k) => labels[k]).join(', ')} dataset${missing.length > 1 ? 's' : ''} to run analysis.`;
        msg.classList.remove('hidden');
      } else {
        msg.classList.add('hidden');
      }
    }
  },

  async loadActiveDatasetsBar() {
    const bar = document.getElementById('active-datasets-bar');
    if (!bar) return;
    try {
      const active = await CF.fetchJSON('/api/analytics/active-datasets');
      if (!active.has_selection) {
        bar.classList.add('hidden');
        bar.innerHTML = '';
        return;
      }
      bar.classList.remove('hidden');
      const badge = (label, ds, type) => {
        if (!ds) return '';
        const rows = ds.success_count || ds.row_count || 0;
        return `<span class="active-ds-badge active-ds-badge-${type}"><span class="badge-type">${label}</span><span class="badge-file">✓ ${CF.escapeHtml(ds.filename)}</span><span class="badge-rows">${rows} rows</span></span>`;
      };
      bar.innerHTML = `<div class="active-ds-inner"><span class="active-ds-title">Active Analysis Datasets</span><div class="active-ds-badges">${badge('Sales', active.sales, 'sales')}${badge('Products', active.products, 'products')}${badge('Inventory', active.inventory, 'inventory')}</div><button type="button" class="btn-secondary text-xs" onclick="CF.openAnalysisModal()">Change datasets</button></div>`;
    } catch {
      bar.classList.add('hidden');
    }
  },

  runAnalysis() {
    CF.openAnalysisModal();
  },

  async executeAnalysis() {
    if (CF.importBusy) {
      CF.toast('Wait for the current import to finish', 'warning');
      return;
    }
    try {
      const prog = await CF.fetchJSON('/api/imports/in-progress');
      if (prog.count > 0) {
        CF.toast('An import is still running. Try analysis again when it completes.', 'warning');
        return;
      }
    } catch {
      /* continue */
    }
    const missing = CF.requiredDatasetTypes().filter((key) => !CF.selection[key]);
    if (missing.length) {
      CF.toast('Select all required datasets before running analysis', 'error');
      CF.updateAnalysisValidation();
      return;
    }

    CF.closeAnalysisModal();
    const body = {
      products_import_id: CF.selection.products?.id ?? null,
      sales_import_id: CF.selection.sales?.id ?? null,
      inventory_import_id: CF.selection.inventory?.id ?? null,
      rebuild_dashboard: document.getElementById('opt-rebuild')?.checked ?? true,
      regenerate_alerts: document.getElementById('opt-alerts')?.checked ?? true,
      recalculate_inventory_risks: document.getElementById('opt-inventory')?.checked ?? true,
      export_report_after: document.getElementById('opt-export')?.checked ?? false,
    };
    const btn = document.getElementById('btn-confirm-analysis');
    if (btn) btn.disabled = true;
    const stageLabels = [
      'Loading dataset…',
      'Validating schema…',
      'Building metrics…',
      'Generating alerts…',
      'Updating dashboard…',
    ];
    let stageIdx = 0;
    const stageTimer = setInterval(() => {
      if (stageIdx < stageLabels.length) CF.toast(stageLabels[stageIdx++], 'info', 1500);
    }, 1000);

    try {
      const pipeline = await CF.fetchJSON('/api/analytics/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      clearInterval(stageTimer);
      CF.showAnalysisStages(pipeline.stages);
      if (!pipeline.success) {
        const err = new Error(pipeline.message || 'Analysis failed');
        err.payload = pipeline;
        CF.showAnalysisError(err);
        return;
      }
      CF.toast(pipeline.message || 'Analysis complete', 'success');
      if (pipeline.post_actions?.length) {
        pipeline.post_actions.forEach((a) => CF.toast(a, 'info', 5000));
      }
      CF.setLastUpdated();
      await CF.loadActiveDatasetsBar();
      document.getElementById('analysis-error-panel')?.remove();
      const path = location.pathname;
      if (path === '/') CF.loadDashboard();
      else if (path === '/products') CF.loadProducts();
      else if (path === '/inventory') CF.loadInventory();
      else if (path === '/profit') CF.loadProfit();
    } catch (e) {
      clearInterval(stageTimer);
      CF.showAnalysisError(e);
    } finally {
      if (btn) btn.disabled = false;
    }
  },

  async generateAlerts() {
    try {
      const r = await CF.fetchJSON('/api/alerts/generate', { method: 'POST' });
      CF.toast(`Generated ${r.generated} alerts`, 'success');
      if (location.pathname === '/alerts') CF.loadAlerts();
    } catch {
      CF.toast('Failed to generate alerts', 'error');
    }
  },

  async loadDashboard() {
    const grid = document.getElementById('metrics-grid');
    const topEl = document.getElementById('top-sellers');
    const recEl = document.getElementById('recommendations');
    CF.showSkeleton('metrics-grid', 'metrics', 8);
    if (topEl) { topEl.innerHTML = CF.skeletonList(5); }
    if (recEl) { recEl.innerHTML = CF.skeletonList(4); }

    try {
      const data = await CF.fetchJSON('/api/analytics/dashboard');
      if (data.requires_dataset_selection) {
        grid.innerHTML = CF.renderOnboardingCard(false);
        CF.renderEmptyCharts();
        if (topEl) topEl.innerHTML = '<p class="empty-state">No analysis yet</p>';
        if (recEl) recEl.innerHTML = '<li class="empty-state">Upload datasets or load a demo company to begin</li>';
        return;
      }
      if (data.requires_analysis_generation) {
        grid.innerHTML = CF.renderPendingAnalysisCard();
        CF.renderEmptyCharts();
        if (topEl) topEl.innerHTML = '<p class="empty-state">No analysis generated yet</p>';
        if (recEl) recEl.innerHTML = '<li class="empty-state">No analysis generated yet</li>';
        const last = document.getElementById('last-updated');
        if (last) { last.textContent = ''; last.classList.add('hidden'); }
        return;
      }
      const m = data.metrics;
      if (data.partial && data.warnings?.length) {
        CF.toast(data.warnings[0], 'warning', 8000);
      }

      grid.innerHTML = [
        CF.metricCard('Total Revenue', CF.formatCurrency(m.total_revenue), null, { accent: true, delay: 0.05 }),
        CF.metricCard('Gross Margin', CF.formatPct(m.gross_margin_pct), `${m.total_orders} orders`, { delay: 0.1 }),
        CF.metricCard('Inventory Efficiency', CF.formatPct(m.inventory_efficiency), null, { delay: 0.15 }),
        CF.metricCard('Operational Risk', CF.formatMetric(m.operational_risk_score, v => Number(v).toFixed(1)), `${m.active_alerts ?? 0} active alerts`, {
          valueClass: (m.operational_risk_score ?? 0) >= 82 ? 'text-orange-400' : 'text-emerald-400',
          delay: 0.2,
        }),
        CF.metricCard('Profit Leakage', CF.formatCurrency(Math.abs(m.profit_leakage_estimate ?? 0)), 'Recoverable exposure', { valueClass: 'text-red-400', delay: 0.25 }),
        CF.metricCard('Dead Inventory', CF.formatCurrency(m.dead_inventory_value), null, { delay: 0.3 }),
        CF.metricCard('Active Products', CF.formatMetric(m.product_count, String), 'In catalog', { delay: 0.35 }),
        CF.metricCard('Avg Order Value', CF.formatCurrency(m.avg_order_value), null, { delay: 0.4 }),
      ].join('');
      CF.reveal(grid);

      CF.chartDefaults();
      CF.renderRevenueChart(data.charts.revenue_trend || []);
      CF.renderCategoryChart(data.charts.category_breakdown || []);

      topEl.innerHTML = (data.top_sellers || []).map((p, i) =>
        CF.listRow(
          p.title || p.sku,
          p.sku,
          `${CF.formatCurrency(p.revenue)} · ${(p.health_score || 0).toFixed(0)}`,
          'positive'
        )
      ).join('') || '<p class="empty-state">Import data to see top sellers</p>';

      recEl.innerHTML = (data.recommendations || [])
        .map(r => `<li class="recommendation-item">${r}</li>`)
        .join('') || '<li class="empty-state">Run analysis for recommendations</li>';

      CF.setLastUpdated();
    } catch (e) {
      CF.toast(CF.parseApiError(e).split('\n')[0] || 'Failed to load dashboard', 'error');
    }
  },

  renderRevenueChart(data) {
    const ctx = document.getElementById('revenueChart');
    if (!ctx) return;
    if (CF.charts.revenue) CF.charts.revenue.destroy();

    const gradient = ctx.getContext('2d').createLinearGradient(0, 0, 0, 280);
    gradient.addColorStop(0, 'rgba(99, 102, 241, 0.25)');
    gradient.addColorStop(1, 'rgba(99, 102, 241, 0)');

    CF.charts.revenue = new Chart(ctx, {
      type: 'line',
      data: {
        labels: data.map((d) => d.date),
        datasets: [{
          label: 'Revenue',
          data: data.map((d) => d.revenue),
          borderColor: '#818cf8',
          backgroundColor: gradient,
          fill: true,
          tension: 0.42,
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 5,
          pointHoverBackgroundColor: '#818cf8',
          pointHoverBorderColor: '#fff',
          pointHoverBorderWidth: 2,
        }],
      },
      options: CF.chartOptions(),
    });
  },

  renderCategoryChart(data) {
    const ctx = document.getElementById('categoryChart');
    if (!ctx) return;
    if (CF.charts.category) CF.charts.category.destroy();

    const palette = ['#6366f1', '#818cf8', '#a5b4fc', '#34d399', '#fbbf24', '#f472b6', '#38bdf8'];
    CF.charts.category = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: data.map((d) => d.category),
        datasets: [{
          data: data.map((d) => d.revenue),
          backgroundColor: palette,
          borderWidth: 0,
          hoverOffset: 6,
        }],
      },
      options: CF.chartOptions({
        cutout: '68%',
        plugins: {
          legend: {
            display: true,
            position: 'bottom',
            labels: {
              color: '#94a3b8',
              boxWidth: 10,
              padding: 14,
              font: { size: 11 },
              usePointStyle: true,
            },
          },
          tooltip: {
            callbacks: {
              label: (ctx) => ` ${CF.formatCurrency(ctx.raw)}`,
            },
          },
        },
        scales: {},
      }),
    });
  },

  tableHTML(headers, rows) {
    if (!rows.length) return '<p class="empty-state">No data available</p>';
    return `<div class="table-wrap"><table class="data-table">
      <thead><tr>${headers.map((h) => `<th>${h}</th>`).join('')}</tr></thead>
      <tbody>${rows.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join('')}</tr>`).join('')}</tbody>
    </table></div>`;
  },

  async loadProducts() {
    CF.showSkeleton('product-summary', 'metrics', 3);
    try {
      const data = await CF.fetchJSON('/api/analytics/products');
      if (data.requires_analysis_generation) {
        CF.showNoAnalysisModule('product-summary', [
          'top-sellers-table', 'worst-table', 'rising-list', 'declining-list',
        ]);
        return;
      }
      const s = data.summary || {};
      const el = document.getElementById('product-summary');
      el.innerHTML = [
        CF.metricCard('Avg Health Score', (s.avg_health_score || 0).toFixed(1), 'Across catalog', { accent: true }),
        CF.metricCard('Rising', String(s.rising_count || 0), 'Products trending up', { valueClass: 'text-emerald-400' }),
        CF.metricCard('Declining', String(s.declining_count || 0), 'Needs attention', { valueClass: 'text-red-400' }),
      ].join('');
      CF.reveal(el);

      const topRows = (data.top_sellers || []).map((p) => [
        p.sku,
        (p.title || '').slice(0, 28),
        CF.formatCurrency(p.revenue),
        (p.health_score || 0).toFixed(0),
        `<span class="badge badge-low">${p.trend_indicator || '—'}</span>`,
      ]);
      document.getElementById('top-sellers-table').innerHTML = CF.tableHTML(
        ['SKU', 'Product', 'Revenue', 'Health', 'Trend'],
        topRows
      );

      const worstRows = (data.worst_performers || []).map((p) => [
        p.sku,
        (p.title || '').slice(0, 28),
        CF.formatCurrency(p.revenue || 0),
        (p.health_score || 0).toFixed(0),
      ]);
      document.getElementById('worst-table').innerHTML = CF.tableHTML(
        ['SKU', 'Product', 'Revenue', 'Health'],
        worstRows
      );

      document.getElementById('rising-list').innerHTML = (data.fast_rising || [])
        .map((p) => CF.listRow(p.title || p.sku, p.sku, '↑ Rising', 'positive'))
        .join('') || '<p class="empty-state">None detected</p>';

      document.getElementById('declining-list').innerHTML = (data.declining || [])
        .map((p) => CF.listRow(p.title || p.sku, p.sku, '↓ Declining', 'negative'))
        .join('') || '<p class="empty-state">None detected</p>';
    } catch {
      CF.toast('Failed to load products', 'error');
    }
  },

  async loadInventory() {
    CF.showSkeleton('inventory-summary', 'metrics', 4);
    try {
      const data = await CF.fetchJSON('/api/analytics/inventory');
      if (data.requires_analysis_generation) {
        CF.showNoAnalysisModule('inventory-summary', ['inventory-alerts', 'reorder-table']);
        return;
      }
      const s = data.summary || {};
      const el = document.getElementById('inventory-summary');
      el.innerHTML = [
        CF.metricCard('Avg Health', (s.avg_health_score || 0).toFixed(1), null, { accent: true }),
        CF.metricCard('Low Stock', String(s.low_stock_count || 0), 'SKUs at risk', { valueClass: 'text-orange-400' }),
        CF.metricCard('Overstock', String(s.overstock_count || 0)),
        CF.metricCard('Dead Inventory', String(s.dead_inventory_count || 0), CF.formatCurrency(s.dead_inventory_value), { valueClass: 'text-red-400' }),
      ].join('');
      CF.reveal(el);

      document.getElementById('inventory-alerts').innerHTML = (data.alerts || [])
        .map((a) => `
        <div class="issue-card">
          <div class="flex justify-between items-start gap-2 mb-2">
            <span class="text-sm font-medium text-white">${a.message}</span>
            ${CF.severityBadge(a.severity)}
          </div>
          <p class="text-xs text-slate-500">${a.recommendation}</p>
        </div>`)
        .join('') || '<p class="empty-state">No inventory alerts</p>';

      const rows = (data.reorder_suggestions || []).map((r) => [
        r.sku,
        r.current_qty,
        r.suggested_reorder,
        r.days_of_cover,
        `<span class="badge badge-${r.urgency === 'high' ? 'critical' : 'medium'}">${r.urgency}</span>`,
      ]);
      document.getElementById('reorder-table').innerHTML = CF.tableHTML(
        ['SKU', 'Qty', 'Reorder', 'Days Cover', 'Urgency'],
        rows
      );
    } catch {
      CF.toast('Failed to load inventory', 'error');
    }
  },

  async loadProfit() {
    CF.showSkeleton('profit-summary', 'metrics', 3);
    try {
      const data = await CF.fetchJSON('/api/analytics/profit-leakage');
      if (data.requires_analysis_generation) {
        const total = document.getElementById('leakage-total');
        if (total) total.textContent = '—';
        CF.showNoAnalysisModule('profit-summary', ['profit-issues', 'profit-recs']);
        return;
      }
      document.getElementById('leakage-total').textContent = CF.formatCurrency(data.total_estimated_leakage);

      const el = document.getElementById('profit-summary');
      el.innerHTML = [
        CF.metricCard('Total Issues', String(data.issue_count || 0), null, { accent: true }),
        CF.metricCard('Critical', String(data.critical_count || 0), null, { valueClass: 'text-red-400' }),
        CF.metricCard('Est. Impact', CF.formatCurrency(data.total_estimated_leakage), null, { valueClass: 'text-red-400' }),
      ].join('');
      CF.reveal(el);

      const filter = document.getElementById('severity-filter')?.value;
      let issues = data.issues || [];
      if (filter) issues = issues.filter((i) => i.severity === filter);

      document.getElementById('profit-issues').innerHTML = issues
        .map((i) => `
        <div class="issue-card">
          <div class="flex justify-between items-start mb-2">
            <span class="text-sm font-medium text-white capitalize">${(i.type || '').replace(/_/g, ' ')}</span>
            ${CF.severityBadge(i.severity)}
          </div>
          <p class="text-sm text-slate-400">${i.message}</p>
          ${i.sku ? `<p class="list-row-meta mt-1">${i.sku}</p>` : ''}
          <p class="text-xs mt-2" style="color:#a5b4fc">→ ${i.recommendation}</p>
        </div>`)
        .join('') || '<p class="empty-state">No profit leakage detected</p>';

      document.getElementById('profit-recs').innerHTML = (data.recommendations || [])
        .map((r) => `<li class="recommendation-item">${r}</li>`)
        .join('');
    } catch {
      CF.toast('Failed to load profit data', 'error');
    }
  },

  async loadAlerts() {
    const list = document.getElementById('alerts-list');
    list.innerHTML = CF.skeletonList(4);
    try {
      const sev = document.getElementById('alert-severity')?.value || '';
      const unread = document.getElementById('unread-only')?.checked || false;
      let url = '/api/alerts?';
      if (sev) url += `severity=${sev}&`;
      if (unread) url += 'unread_only=true&';
      const alerts = await CF.fetchJSON(url);

      list.innerHTML = alerts
        .map((a) => `
        <div class="card card-padded ${a.is_read ? 'opacity-70' : ''}" style="display:flex;gap:1rem;align-items:flex-start">
          <div class="flex-1 min-w-0">
            <div class="flex flex-wrap items-center gap-2 mb-2">
              ${CF.severityBadge(a.severity)}
              <span class="text-xs text-slate-500">${a.alert_type}</span>
              <span class="text-xs text-slate-600 ml-auto">${CF.formatDateTime(a.created_at)}</span>
            </div>
            <h4 class="font-semibold text-white text-sm">${a.title}</h4>
            <p class="text-sm text-slate-400 mt-1">${a.message}</p>
          </div>
          <div class="flex flex-col gap-1 shrink-0">
            <button type="button" onclick="CF.markRead(${a.id})" class="btn-secondary text-xs py-1 px-2">Read</button>
            <button type="button" onclick="CF.dismissAlert(${a.id})" class="btn-secondary text-xs py-1 px-2">Dismiss</button>
          </div>
        </div>`)
        .join('') || '<p class="empty-state">No alerts — run analysis and generate alerts</p>';
    } catch {
      CF.toast('Failed to load alerts', 'error');
    }
  },

  async markRead(id) {
    await CF.fetchJSON(`/api/alerts/${id}/read`, { method: 'PATCH' });
    CF.loadAlerts();
  },

  async dismissAlert(id) {
    await CF.fetchJSON(`/api/alerts/${id}/dismiss`, { method: 'PATCH' });
    CF.loadAlerts();
  },

  initImports() {
    const dropzone = document.getElementById('dropzone');
    const input = document.getElementById('file-input');
    if (!dropzone || !input) return;

    dropzone.addEventListener('click', (e) => {
      if (e.target.tagName !== 'SELECT' && e.target.tagName !== 'BUTTON') input.click();
    });
    dropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    });
    dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
    dropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
      if (e.dataTransfer.files.length) CF.uploadFile(e.dataTransfer.files[0]);
    });
    input.addEventListener('change', () => {
      if (input.files.length) CF.uploadFile(input.files[0]);
    });
    CF.loadImportHistory();
  },

  async uploadFile(file) {
    if (CF.importBusy) {
      CF.toast('An import is already running', 'warning');
      return;
    }
    const form = new FormData();
    form.append('file', file);
    form.append('source_type', document.getElementById('source-type')?.value || 'generic');
    form.append('dataset_type', document.getElementById('dataset-type')?.value || 'auto');
    const status = document.getElementById('upload-status');
    if (status) {
      status.classList.remove('hidden');
      status.innerHTML = '<div class="import-progress-banner">Uploading file…</div>';
    }
    CF.importBusy = true;
    try {
      const r = await CF.fetchJSON('/api/imports/upload', { method: 'POST', body: form });
      const final = await CF.waitForImport(r.id, {
        onTick: (tick) => CF.updateUploadStatusBanner(tick),
      });
      CF.presentImportOutcome(final, status);
    } catch (e) {
      if (status) status.innerHTML = '<div class="toast toast-error">Upload failed</div>';
      CF.toast(CF.parseApiError(e).split('\n')[0] || 'Upload failed', 'error');
      await CF.loadImportHistory();
    } finally {
      CF.updateImportBusyState();
    }
  },

  pendingConfirmImportId: null,
  importHistoryRecords: [],
  importBusy: false,
  importPollTimer: null,
  _trackedImportIds: new Set(),
  _importWaiters: new Map(),
  _importSyncBusy: false,
  _importHistoryGen: 0,
  _importHistoryRefreshTimer: null,
  _terminalHandled: new Set(),
  IMPORT_POLL_MS: 400,

  importStatusLabel(status) {
    const map = {
      importing: 'Importing',
      processing: 'Processing',
      completed: 'Completed',
      failed: 'Failed',
      pending_confirm: 'Confirm type',
    };
    return map[status] || status;
  },

  importNeedsPolling(record) {
    return Boolean(record?.id && !['completed', 'failed', 'pending_confirm'].includes(record.status));
  },

  trackImport(importId) {
    if (importId == null) return;
    CF._terminalHandled.delete(importId);
    CF._trackedImportIds.add(importId);
    CF.importBusy = true;
    CF.startImportSync();
  },

  untrackImport(importId) {
    CF._trackedImportIds.delete(importId);
    CF._importWaiters.delete(importId);
  },

  updateImportBusyState() {
    CF.importBusy = CF._trackedImportIds.size > 0 || CF._importWaiters.size > 0;
    document.body.classList.toggle('import-in-progress', CF.importBusy);
  },

  startImportSync() {
    if (CF.importPollTimer != null) return;
    CF.importPollTimer = setInterval(() => {
      CF.tickImportSync().catch(() => {});
    }, CF.IMPORT_POLL_MS);
    CF.tickImportSync().catch(() => {});
  },

  stopImportSyncIfIdle() {
    if (CF._trackedImportIds.size || CF._importWaiters.size) return;
    if (CF.importPollTimer != null) {
      clearInterval(CF.importPollTimer);
      CF.importPollTimer = null;
    }
    CF.updateImportBusyState();
  },

  scheduleImportHistoryRefresh() {
    if (!document.getElementById('import-history')) return;
    clearTimeout(CF._importHistoryRefreshTimer);
    CF._importHistoryRefreshTimer = setTimeout(() => {
      CF.loadImportHistory();
    }, 120);
  },

  updateUploadStatusBanner(record) {
    const status = document.getElementById('upload-status');
    if (!status || !record) return;
    status.classList.remove('hidden');
    if (['completed', 'failed', 'pending_confirm'].includes(record.status)) return;
    status.innerHTML = `<div class="import-progress-banner">${CF.importStatusLabel(record.status)}…</div>`;
  },

  presentImportOutcome(record, statusEl) {
    if (!record) return;
    if (record.needs_type_confirmation || record.status === 'pending_confirm') {
      if (statusEl) {
        statusEl.innerHTML = '<div class="toast toast-warning">Please confirm dataset type</div>';
      }
      CF.openTypeConfirmModal(record);
      return;
    }
    if (record.status === 'completed') {
      const dtype = (record.dataset_type || 'unknown').toLowerCase();
      if (statusEl) {
        statusEl.innerHTML = `<div class="toast toast-success">${CF.datasetTypeBadge(dtype)} · ${record.success_count} rows imported</div>`;
      }
      CF.toast(`Import complete · ${CF.datasetTypeLabel(dtype)}`, 'success');
    }
  },

  waitForImport(importId, handlers = {}) {
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        if (!CF._importWaiters.has(importId)) return;
        CF.untrackImport(importId);
        CF.updateImportBusyState();
        CF.stopImportSyncIfIdle();
        reject(new Error('Import timed out. Check Import History for status.'));
      }, 600000);

      const attachWaiter = () => ({
        resolve: (record) => {
          clearTimeout(timeout);
          resolve(record);
        },
        reject: (err) => {
          clearTimeout(timeout);
          reject(err);
        },
        handlers,
      });

      const onStatus = async (record) => {
        handlers.onTick?.(record);
        CF.updateUploadStatusBanner(record);
        if (CF.importNeedsPolling(record)) {
          CF._importWaiters.set(importId, attachWaiter());
          CF.trackImport(importId);
          return;
        }
        CF._importWaiters.set(importId, attachWaiter());
        await CF.handleImportTerminal(record);
      };

      CF.fetchJSON(`/api/imports/${importId}/status`).then(onStatus).catch((err) => {
        clearTimeout(timeout);
        reject(err);
      });
    });
  },

  async handleImportTerminal(record) {
    const importId = record.id;
    if (CF._terminalHandled.has(importId)) return;
    CF._terminalHandled.add(importId);

    const waiter = CF._importWaiters.get(importId);
    CF.untrackImport(importId);
    waiter?.handlers?.onTick?.(record);
    await CF.refreshAfterImport({ immediate: true });

    if (waiter) {
      if (record.status === 'failed') {
        const err = new Error('Import failed');
        err.payload = record;
        waiter.reject(err);
      } else {
        waiter.resolve(record);
      }
    } else {
      CF.presentImportOutcome(record, document.getElementById('upload-status'));
    }

    CF.updateImportBusyState();
    CF.stopImportSyncIfIdle();
  },

  async tickImportSync() {
    if (CF._importSyncBusy) return;
    CF._importSyncBusy = true;
    try {
      const ids = new Set(CF._trackedImportIds);
      try {
        const prog = await CF.fetchJSON('/api/imports/in-progress');
        (prog.in_progress || []).forEach((job) => ids.add(job.id));
        if (prog.count) CF.importBusy = true;
      } catch {
        /* keep local tracked ids */
      }

      if (!ids.size) {
        CF.stopImportSyncIfIdle();
        return;
      }

      for (const importId of ids) {
        let record;
        try {
          record = await CF.fetchJSON(`/api/imports/${importId}/status`);
        } catch {
          continue;
        }

        const waiter = CF._importWaiters.get(importId);
        waiter?.handlers?.onTick?.(record);
        CF.updateUploadStatusBanner(record);

        if (CF.importNeedsPolling(record)) {
          CF.trackImport(importId);
          CF.scheduleImportHistoryRefresh();
          continue;
        }

        await CF.handleImportTerminal(record);
      }
    } finally {
      CF._importSyncBusy = false;
    }
  },

  async syncImportsOnLoad() {
    try {
      const data = await CF.fetchJSON('/api/imports/in-progress');
      if (!data.count || !data.in_progress?.length) return;
      const status = document.getElementById('upload-status');
      if (status) {
        status.classList.remove('hidden');
        status.innerHTML = '<div class="import-progress-banner">Import in progress…</div>';
      }
      for (const job of data.in_progress) {
        CF.trackImport(job.id);
      }
    } catch {
      /* optional on pages without API */
    }
  },

  async pollImportUntilDone(importId, handlers = {}) {
    return CF.waitForImport(importId, handlers);
  },

  async refreshAfterImport({ immediate = false } = {}) {
    CF.catalog = null;
    const tasks = [CF.loadActiveDatasetsBar()];
    if (document.getElementById('import-history')) {
      if (immediate) {
        clearTimeout(CF._importHistoryRefreshTimer);
        tasks.push(CF.loadImportHistory());
      } else {
        CF.scheduleImportHistoryRefresh();
      }
    }
    await Promise.all(tasks);
    CF.refreshPlatformUI();
  },

  selectedImportIds: new Set(),
  deleteImportMode: null,
  deleteImportTargetId: null,

  openTypeConfirmModal(record) {
    CF.pendingConfirmImportId = record.id;
    const modal = document.getElementById('type-confirm-modal');
    if (!modal) return;
    document.getElementById('type-confirm-filename').textContent =
      record.display_name || record.filename;
    const conf = record.detection_confidence != null
      ? `Detection confidence: ${Math.round(record.detection_confidence * 100)}%.`
      : '';
    const reason = record.detection_reason
      ? record.detection_reason
      : 'We could not confidently classify this file from its column structure.';
    document.getElementById('type-confirm-sub').textContent =
      `${reason} ${conf}`.trim();
    modal.style.display = 'flex';
    modal.setAttribute('aria-hidden', 'false');
  },

  closeTypeConfirmModal() {
    const modal = document.getElementById('type-confirm-modal');
    if (!modal) return;
    modal.style.display = 'none';
    modal.setAttribute('aria-hidden', 'true');
    CF.pendingConfirmImportId = null;
  },

  async confirmImportType(type) {
    const id = CF.pendingConfirmImportId;
    if (!id || CF.importBusy) return;
    const status = document.getElementById('upload-status');
    CF.importBusy = true;
    try {
      const r = await CF.fetchJSON(`/api/imports/${id}/confirm-type`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dataset_type: type }),
      });
      CF.closeTypeConfirmModal();
      if (status) {
        status.classList.remove('hidden');
        status.innerHTML = '<div class="import-progress-banner">Processing confirmed type…</div>';
      }
      const final = await CF.waitForImport(id, {
        onTick: (tick) => CF.updateUploadStatusBanner(tick),
      });
      if (final.status === 'completed') {
        CF.toast(`${CF.datasetTypeLabel(type)} confirmed · ${final.success_count} rows`, 'success');
        if (status) {
          status.innerHTML = `<div class="toast toast-success">${CF.datasetTypeBadge(type)} · ${final.success_count} rows imported</div>`;
        }
      } else {
        CF.presentImportOutcome(final, status);
      }
    } catch (e) {
      CF.toast(CF.parseApiError(e).split('\n')[0] || 'Could not confirm dataset type', 'error');
    } finally {
      CF.updateImportBusyState();
    }
  },

  openTypeConfirmById(id) {
    CF.fetchJSON('/api/imports/history').then((records) => {
      const r = records.find((x) => x.id === id);
      if (r) CF.openTypeConfirmModal(r);
    });
  },

  async loadImportHistory() {
    const container = document.getElementById('import-history');
    const countEl = document.getElementById('import-history-count');
    if (!container) return;
    const gen = ++CF._importHistoryGen;
    try {
      const records = await CF.fetchJSON('/api/imports/history');
      if (gen !== CF._importHistoryGen) return;
      CF.importHistoryRecords = records;
      CF.selectedImportIds = new Set(
        [...CF.selectedImportIds].filter((id) => records.some((r) => r.id === id))
      );
      if (countEl) {
        countEl.textContent = records.length
          ? `${records.length} dataset${records.length === 1 ? '' : 's'}`
          : 'No datasets imported yet';
      }
      const selectAll = document.getElementById('import-select-all');
      if (selectAll) {
        selectAll.checked = records.length > 0 && CF.selectedImportIds.size === records.length;
        selectAll.indeterminate = CF.selectedImportIds.size > 0 && CF.selectedImportIds.size < records.length;
      }
      CF.updateImportBulkButtons();
      if (!records.length) {
        container.innerHTML = '<div class="import-empty-state"><p>No imports yet</p><p class="text-sm text-slate-500 mt-1">Upload a file to get started</p></div>';
        return;
      }
      container.innerHTML = records.map((r) => CF.renderImportCard(r)).join('');
    } catch {
      container.innerHTML = '<p class="empty-state">Could not load import history</p>';
    }
  },

  renderImportCard(r) {
    const dtype = (r.dataset_type || 'unknown').toLowerCase();
    const rows = r.success_count || r.row_count || 0;
    const title = r.display_name || r.filename;
    const uploaded = r.started_at
      ? CF.formatDateShort(r.started_at)
      : '';
    const checked = CF.selectedImportIds.has(r.id) ? 'checked' : '';
    const inProgress = r.status === 'importing' || r.status === 'processing';
    const statusCls = r.status === 'completed'
      ? 'import-status-ok'
      : r.status === 'failed'
        ? 'import-status-fail'
        : inProgress
          ? 'import-status-busy'
          : 'import-status-pending';
    const statusTitle = CF.importStatusLabel(r.status);
    return `
    <article class="import-card${inProgress ? ' import-card-busy' : ''}" data-import-id="${r.id}">
      <label class="import-card-check">
        <input type="checkbox" class="import-row-check" data-id="${r.id}" ${checked} onchange="CF.toggleImportSelect(${r.id}, this.checked)">
      </label>
      <div class="import-card-body">
        <div class="import-card-top">
          <p class="import-card-title">${CF.escapeHtml(title)}</p>
          <span class="import-status-dot ${statusCls}" title="${statusTitle}"></span>
        </div>
        ${r.filename !== title ? `<p class="import-filename-hint">${CF.escapeHtml(r.filename)}</p>` : ''}
        <div class="import-card-meta">
          ${CF.datasetTypeShortBadge(dtype)}
          <span class="import-meta-item">${inProgress ? statusTitle : `${rows.toLocaleString()} rows`}</span>
          <span class="import-meta-item">${CF.escapeHtml(uploaded)}</span>
        </div>
        ${r.needs_type_confirmation
          ? `<div class="import-confirm-row"><span class="badge-dataset badge-dataset-confirm">Needs type</span>
             <button type="button" class="btn-secondary text-xs" onclick="CF.openTypeConfirmById(${r.id})">Confirm</button></div>`
          : ''}
      </div>
      <div class="import-card-actions">
        <button type="button" class="import-delete-btn" title="Delete dataset" onclick="CF.openDeleteImportModal('single', ${r.id})" aria-label="Delete">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="18" height="18"><path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
        </button>
      </div>
    </article>`;
  },

  toggleImportSelect(id, checked) {
    if (checked) CF.selectedImportIds.add(id);
    else CF.selectedImportIds.delete(id);
    const records = CF.importHistoryRecords;
    const selectAll = document.getElementById('import-select-all');
    if (selectAll) {
      selectAll.checked = records.length > 0 && CF.selectedImportIds.size === records.length;
      selectAll.indeterminate = CF.selectedImportIds.size > 0 && CF.selectedImportIds.size < records.length;
    }
    CF.updateImportBulkButtons();
  },

  toggleSelectAllImports(checked) {
    CF.selectedImportIds = checked ? new Set(CF.importHistoryRecords.map((r) => r.id)) : new Set();
    document.querySelectorAll('.import-row-check').forEach((el) => { el.checked = checked; });
    const selectAll = document.getElementById('import-select-all');
    if (selectAll) selectAll.indeterminate = false;
    CF.updateImportBulkButtons();
  },

  updateImportBulkButtons() {
    const btn = document.getElementById('btn-delete-selected');
    if (btn) btn.disabled = CF.selectedImportIds.size === 0;
  },

  openDeleteImportModal(mode, importId = null) {
    CF.deleteImportMode = mode;
    CF.deleteImportTargetId = importId;
    const modal = document.getElementById('delete-import-modal');
    if (!modal) return;
    const sub = document.getElementById('delete-import-sub');
    const target = document.getElementById('delete-import-target');
    if (mode === 'single' && importId) {
      const rec = CF.importHistoryRecords.find((r) => r.id === importId);
      sub.textContent = 'Are you sure you want to remove this imported dataset?';
      target.textContent = rec ? (rec.display_name || rec.filename) : '';
    } else if (mode === 'bulk') {
      sub.textContent = `Remove ${CF.selectedImportIds.size} selected dataset(s)?`;
      target.textContent = 'Selected imports will be removed from analysis.';
    } else {
      sub.textContent = 'Remove all imported datasets from your workspace?';
      target.textContent = `${CF.importHistoryRecords.length} dataset(s) will be cleared.`;
    }
    modal.style.display = 'flex';
    modal.setAttribute('aria-hidden', 'false');
  },

  closeDeleteImportModal() {
    const modal = document.getElementById('delete-import-modal');
    if (!modal) return;
    modal.style.display = 'none';
    modal.setAttribute('aria-hidden', 'true');
    CF.deleteImportMode = null;
    CF.deleteImportTargetId = null;
  },

  async confirmDeleteImport() {
    const mode = CF.deleteImportMode;
    const btn = document.getElementById('btn-confirm-delete-import');
    if (btn) btn.disabled = true;
    try {
      if (mode === 'single' && CF.deleteImportTargetId) {
        await CF.fetchJSON(`/api/imports/${CF.deleteImportTargetId}`, { method: 'DELETE' });
        CF.toast('Dataset removed', 'success');
      } else if (mode === 'bulk') {
        const ids = [...CF.selectedImportIds];
        if (!ids.length) return;
        await CF.fetchJSON('/api/imports/bulk-delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ import_ids: ids }),
        });
        CF.selectedImportIds.clear();
        CF.toast(`Removed ${ids.length} dataset(s)`, 'success');
      } else if (mode === 'all') {
        await CF.fetchJSON('/api/admin/clear-import-history', { method: 'POST' });
        CF.selectedImportIds.clear();
        CF.toast('Import history cleared', 'success');
      }
      CF.closeDeleteImportModal();
      CF.catalog = null;
      CF.selection = { sales: null, products: null, inventory: null };
      await CF.loadActiveDatasetsBar();
      await CF.loadImportHistory();
    } catch (e) {
      CF.toast(CF.parseApiError(e).split('\n')[0] || 'Delete failed', 'error');
    } finally {
      if (btn) btn.disabled = false;
    }
  },

  renderPendingAnalysisCard(compact = false) {
    if (compact) {
      return `<div class="card card-padded onboarding-panel">
        <p class="text-white font-medium mb-2">No analysis generated yet</p>
        <p class="text-sm text-slate-500 mb-4">Datasets are selected. Run analysis to populate metrics and charts.</p>
        <button type="button" class="btn-primary" onclick="CF.openAnalysisModal()">Run Analysis</button>
      </div>`;
    }
    return `<div class="card card-padded col-span-full onboarding-panel">
      <h3 class="text-white font-semibold text-lg mb-2">No analysis generated yet</h3>
      <p class="text-sm text-slate-400 mb-2">Your imported datasets are ready, but no intelligence has been generated.</p>
      <p class="text-sm text-slate-500 mb-5">Click Run Analysis to build KPIs, charts, alerts, and recommendations.</p>
      <button type="button" class="btn-primary" onclick="CF.openAnalysisModal()">Run Analysis</button>
    </div>`;
  },

  showNoAnalysisModule(summaryId, extraIds = []) {
    const el = document.getElementById(summaryId);
    if (el) {
      el.innerHTML = CF.renderPendingAnalysisCard(true);
      CF.reveal(el);
    }
    extraIds.forEach((id) => {
      const node = document.getElementById(id);
      if (node) node.innerHTML = '<p class="empty-state">No analysis generated yet</p>';
    });
  },

  renderOnboardingCard(compact = false) {
    if (compact) {
      return `<div class="card card-padded onboarding-panel">
        <p class="text-white font-medium mb-2">No analysis yet</p>
        <p class="text-sm text-slate-500 mb-4">Upload your sales, products, and inventory data to begin.</p>
        <button type="button" class="btn-primary" onclick="location.href='/imports'">Upload Data</button>
      </div>`;
    }
    return `<div class="card card-padded col-span-full onboarding-panel">
      <h3 class="text-white font-semibold text-lg mb-2">Welcome to CommerceFlow</h3>
      <p class="text-sm text-slate-400 mb-2">No revenue, charts, or alerts yet.</p>
      <p class="text-sm text-slate-500 mb-5">Upload your business datasets to run analysis.</p>
      <div class="flex flex-wrap gap-3">
        <button type="button" class="btn-primary" onclick="location.href='/imports'">Upload Data</button>
        <button type="button" class="btn-secondary" onclick="CF.openAnalysisModal()">Select Datasets</button>
      </div>
    </div>`;
  },

  renderEmptyCharts() {
    CF.chartDefaults();
    CF.renderRevenueChart([]);
    CF.renderCategoryChart([]);
  },

  clearAnalysisUIState() {
    CF.exportMeta = null;
    if (CF.exportPollTimer) {
      clearInterval(CF.exportPollTimer);
      CF.exportPollTimer = null;
    }
    Object.keys(CF.charts).forEach((k) => {
      if (CF.charts[k]) { CF.charts[k].destroy(); delete CF.charts[k]; }
    });
    const last = document.getElementById('last-updated');
    if (last) { last.textContent = ''; last.classList.add('hidden'); }
    document.getElementById('analysis-error-panel')?.remove();
  },

  clearLocalState() {
    CF.selection = { sales: null, products: null, inventory: null };
    CF.catalog = null;
    CF.platformStatus = null;
    try { localStorage.clear(); sessionStorage.clear(); } catch { /* ignore */ }
    CF.clearAnalysisUIState();
  },

  async refreshPlatformUI() {
    try {
      CF.platformStatus = await CF.fetchJSON('/api/admin/platform-status');
    } catch { /* silent */ }
  },

  openClearDatasetsModal() {
    const modal = document.getElementById('clear-datasets-modal');
    if (!modal) return;
    document.getElementById('clear-datasets-progress')?.classList.add('hidden');
    modal.style.display = 'flex';
    modal.setAttribute('aria-hidden', 'false');
  },

  closeClearDatasetsModal() {
    const modal = document.getElementById('clear-datasets-modal');
    if (!modal) return;
    modal.style.display = 'none';
    modal.setAttribute('aria-hidden', 'true');
    document.getElementById('clear-datasets-progress')?.classList.add('hidden');
  },

  openResetAnalysisModal() {
    const modal = document.getElementById('reset-analysis-modal');
    if (!modal) return;
    document.getElementById('reset-analysis-progress')?.classList.add('hidden');
    modal.style.display = 'flex';
    modal.setAttribute('aria-hidden', 'false');
  },

  closeResetAnalysisModal() {
    const modal = document.getElementById('reset-analysis-modal');
    if (!modal) return;
    modal.style.display = 'none';
    modal.setAttribute('aria-hidden', 'true');
    document.getElementById('reset-analysis-progress')?.classList.add('hidden');
  },

  _setResetProgress(prefix, show, label) {
    const panel = document.getElementById(`${prefix}-progress`);
    const lbl = document.getElementById(`${prefix}-progress-label`);
    if (panel) panel.classList.toggle('hidden', !show);
    if (lbl && label) lbl.textContent = label;
  },

  async confirmClearDatasets() {
    const btn = document.getElementById('btn-confirm-clear-datasets');
    if (btn) btn.disabled = true;
    CF._setResetProgress('clear-datasets', true, 'Clearing imported datasets…');
    try {
      const r = await CF.fetchJSON('/api/admin/clear-imported-datasets', { method: 'POST' });
      CF.closeClearDatasetsModal();
      CF.clearLocalState();
      await CF.loadActiveDatasetsBar();
      await CF.refreshPlatformUI();
      CF.toast(r.message || 'Imported datasets cleared', 'success');
      CF.refreshCurrentPage();
    } catch (e) {
      CF.toast(CF.parseApiError(e).split('\n')[0] || 'Clear failed', 'error');
    } finally {
      CF._setResetProgress('clear-datasets', false);
      if (btn) btn.disabled = false;
    }
  },

  async confirmResetAnalysis() {
    const btn = document.getElementById('btn-confirm-reset-analysis');
    if (btn) btn.disabled = true;
    CF._setResetProgress('reset-analysis', true, 'Resetting analysis…');
    try {
      const r = await CF.fetchJSON('/api/admin/reset-analysis', { method: 'POST' });
      CF.closeResetAnalysisModal();
      CF.clearAnalysisUIState();
      await CF.loadActiveDatasetsBar();
      await CF.refreshPlatformUI();
      CF.toast(r.message || 'Analysis results cleared', 'success', 6000);
      CF.refreshCurrentPage();
    } catch (e) {
      CF.toast(CF.parseApiError(e).split('\n')[0] || 'Reset failed', 'error');
    } finally {
      CF._setResetProgress('reset-analysis', false);
      if (btn) btn.disabled = false;
    }
  },

  /** @deprecated */
  openRebuildAnalyticsModal() { CF.openResetAnalysisModal(); },
  closeRebuildAnalyticsModal() { CF.closeResetAnalysisModal(); },
  confirmRebuildAnalytics() { return CF.confirmResetAnalysis(); },

  /** @deprecated use openClearDatasetsModal / openResetAnalysisModal */
  openResetModal(mode) {
    if (mode === 'full') CF.openResetAnalysisModal();
    else CF.openClearDatasetsModal();
  },
  closeResetModal() {
    CF.closeClearDatasetsModal();
    CF.closeResetAnalysisModal();
  },

  refreshCurrentPage() {
    const path = location.pathname;
    if (path === '/') CF.loadDashboard();
    else if (path === '/imports') CF.loadImportHistory();
    else if (path === '/products') CF.loadProducts();
    else if (path === '/inventory') CF.loadInventory();
    else if (path === '/profit') CF.loadProfit();
    else if (path === '/alerts') CF.loadAlerts();
    else if (path === '/reports') CF.loadReports();
  },

  async loadDemoCompany(company) {
    const label = company.charAt(0).toUpperCase() + company.slice(1);
    CF.toast(`Loading ${label} demo…`, 'info', 12000);
    try {
      const r = await CF.fetchJSON(`/api/admin/demo/load/${company}`, { method: 'POST' });
      CF.clearLocalState();
      await CF.loadActiveDatasetsBar();
      await CF.refreshPlatformUI();
      CF.toast(r.message || `${label} demo loaded`, 'success', 6000);
      if (location.pathname !== '/') location.href = '/';
      else CF.loadDashboard();
    } catch (e) {
      CF.toast(CF.parseApiError(e).split('\n')[0] || 'Demo load failed', 'error', 8000);
    }
  },

  exportMeta: null,
  exportPollTimer: null,

  EXPORT_CARDS: [
    { id: 'summary', title: 'Executive Summary', desc: 'KPIs, metric traces, and dashboard rollups from active datasets.', icon: 'chart' },
    { id: 'products', title: 'Products', desc: 'Catalog export with margins, health scores, and trends.', icon: 'box' },
    { id: 'inventory', title: 'Inventory', desc: 'Stock levels, risk flags, days in stock, and health scores.', icon: 'layers' },
    { id: 'sales', title: 'Sales', desc: 'Transaction-level revenue export. Streaming CSV for large datasets.', icon: 'trend' },
    { id: 'alerts', title: 'Alerts', desc: 'Operational alerts with severity, type, and timestamps.', icon: 'bell' },
    { id: 'profit_leakage', title: 'Profit Leakage', desc: 'Recoverable margin issues, impact estimates, and recommendations.', icon: 'leak' },
  ],

  exportIcon(name) {
    const icons = {
      chart: '<path stroke-linecap="round" stroke-linejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>',
      box: '<path stroke-linecap="round" stroke-linejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/>',
      layers: '<path stroke-linecap="round" stroke-linejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/>',
      trend: '<path stroke-linecap="round" stroke-linejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/>',
      bell: '<path stroke-linecap="round" stroke-linejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/>',
      leak: '<path stroke-linecap="round" stroke-linejoin="round" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>',
    };
    return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">${icons[name] || icons.chart}</svg>`;
  },

  formatRowCount(n) {
    if (n == null) return '—';
    if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
    if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
    return String(n);
  },

  async loadReports() {
    const grid = document.getElementById('export-grid');
    const empty = document.getElementById('export-empty-selection');
    if (!grid) return;

    try {
      CF.exportMeta = await CF.fetchJSON('/api/exports/meta');
      const m = CF.exportMeta;
      const rc = m.row_counts || {};

      document.getElementById('export-summary-badges').innerHTML = [
        `<span class="export-stat-badge"><strong>${CF.formatRowCount(rc.products)}</strong> products</span>`,
        `<span class="export-stat-badge"><strong>${CF.formatRowCount(rc.sales)}</strong> sales rows</span>`,
        `<span class="export-stat-badge"><strong>${CF.formatRowCount(rc.alerts)}</strong> alerts</span>`,
        `<span class="export-stat-badge"><strong>${m.enterprise_sheets || 5}</strong> sheets</span>`,
      ].join('');

      const total = m.total_rows || 0;
      document.getElementById('export-dataset-size').textContent =
        m.has_selection ? `${CF.formatRowCount(total)} rows` : 'No selection';
      document.getElementById('export-est-size').textContent =
        m.estimated_sizes?.enterprise?.human || '—';

      const last = m.last_export;
      document.getElementById('export-last-generated').textContent = last?.completed_at
        ? CF.formatDateTime(last.completed_at)
        : 'Not yet generated';

      CF.setExportStatus('ready', 'Ready');

      if (!m.has_selection) {
        grid.classList.add('hidden');
        empty?.classList.remove('hidden');
        if (empty) empty.innerHTML = '<p class="text-white font-medium mb-2">No datasets selected</p><p class="text-sm text-slate-500">Select imports and run analysis before exporting.</p>';
        document.getElementById('btn-enterprise-export').disabled = true;
        return;
      }

      if (!m.has_generated_analysis) {
        grid.classList.add('hidden');
        empty?.classList.remove('hidden');
        if (empty) {
          empty.innerHTML = '<p class="text-white font-medium mb-2">No analysis generated yet</p><p class="text-sm text-slate-500 mb-4">Run Analysis to generate exportable intelligence.</p><button type="button" class="btn-primary" onclick="CF.openAnalysisModal()">Run Analysis</button>';
        }
        document.getElementById('btn-enterprise-export').disabled = true;
        document.getElementById('export-last-generated').textContent = 'Not yet generated';
        return;
      }

      empty?.classList.add('hidden');
      grid.classList.remove('hidden');
      document.getElementById('btn-enterprise-export').disabled = false;

      const est = m.estimated_sizes || {};
      grid.innerHTML = CF.EXPORT_CARDS.map((card) => {
        const rowKey = card.id === 'profit_leakage' ? 'products' : card.id === 'summary' ? 'products' : card.id;
        const rows = rc[rowKey] ?? rc.alerts ?? 0;
        const sizeHint = est[card.id]?.human || '';
        return `
          <article class="export-card">
            <div class="export-card-icon">${CF.exportIcon(card.icon)}</div>
            <h3 class="export-card-title">${card.title}</h3>
            <p class="export-card-desc">${card.desc}</p>
            <div class="export-card-meta">
              <span>${CF.formatRowCount(rows)} rows</span>
              ${sizeHint ? `<span>~${sizeHint}</span>` : ''}
            </div>
            <div class="export-card-actions">
              <button type="button" class="export-format-btn" onclick="CF.exportReport('${card.id}', 'csv')" title="CSV">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg> CSV
              </button>
              <button type="button" class="export-format-btn" onclick="CF.exportReport('${card.id}', 'xlsx')" title="XLSX">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg> XLSX
              </button>
              <button type="button" class="export-format-btn" onclick="CF.exportReport('${card.id}', 'json')" title="JSON">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"/></svg> JSON
              </button>
            </div>
          </article>`;
      }).join('');
      CF.reveal(grid);
    } catch (e) {
      CF.toast(CF.parseApiError(e).split('\n')[0] || 'Failed to load export center', 'error');
    }
  },

  setExportStatus(state, label) {
    const el = document.getElementById('export-status');
    if (!el) return;
    el.textContent = label;
    el.className = 'export-meta-value export-status-pill' + (state === 'running' ? ' running' : state === 'failed' ? ' failed' : '');
  },

  showExportProgress(show) {
    document.getElementById('export-progress-panel')?.classList.toggle('hidden', !show);
  },

  updateExportProgress(pct, message, title) {
    const fill = document.getElementById('export-progress-fill');
    const pctEl = document.getElementById('export-progress-pct');
    const msg = document.getElementById('export-progress-message');
    const tit = document.getElementById('export-progress-title');
    if (fill) fill.style.width = `${pct}%`;
    if (pctEl) pctEl.textContent = `${pct}%`;
    if (msg && message) msg.textContent = message;
    if (tit && title) tit.textContent = title;
  },

  async startEnterpriseExport() {
    await CF.startExportJob('enterprise', 'xlsx');
  },

  async startExportJob(reportType, format) {
    CF.showExportProgress(true);
    CF.setExportStatus('running', 'Processing');
    CF.updateExportProgress(0, 'Queuing export job…', 'Generating export…');
    document.getElementById('btn-enterprise-export')?.setAttribute('disabled', 'true');

    try {
      const res = await CF.fetchJSON('/api/exports/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ report_type: reportType, format }),
      });
      await CF.pollExportJob(res.job.id, reportType);
    } catch (e) {
      CF.setExportStatus('failed', 'Failed');
      CF.showExportProgress(false);
      CF.toast(CF.parseApiError(e).split('\n')[0] || 'Export failed', 'error');
    } finally {
      document.getElementById('btn-enterprise-export')?.removeAttribute('disabled');
    }
  },

  async pollExportJob(jobId, reportType) {
    if (CF.exportPollTimer) clearInterval(CF.exportPollTimer);

    const tick = async () => {
      try {
        const job = await CF.fetchJSON(`/api/exports/jobs/${jobId}`);
        CF.updateExportProgress(job.progress || 0, job.message, `Exporting ${reportType.replace(/_/g, ' ')}…`);

        if (job.status === 'completed') {
          clearInterval(CF.exportPollTimer);
          CF.exportPollTimer = null;
          CF.updateExportProgress(100, 'Download starting…', 'Complete');
          CF.setExportStatus('ready', 'Ready');
          const a = document.createElement('a');
          a.href = job.download_url;
          a.download = job.filename || 'export.bin';
          a.click();
          CF.toast('Export ready — download started', 'success');
          setTimeout(() => CF.showExportProgress(false), 1200);
          CF.loadReports();
          return;
        }
        if (job.status === 'failed') {
          clearInterval(CF.exportPollTimer);
          CF.exportPollTimer = null;
          CF.setExportStatus('failed', 'Failed');
          CF.showExportProgress(false);
          CF.toast(job.error || 'Export failed', 'error');
        }
      } catch {
        clearInterval(CF.exportPollTimer);
        CF.setExportStatus('failed', 'Failed');
        CF.showExportProgress(false);
      }
    };

    await tick();
    CF.exportPollTimer = setInterval(tick, 800);
  },

  async exportReport(type, format) {
    const useAsync =
      type === 'enterprise' ||
      (type === 'sales' && format === 'csv' && CF.exportMeta?.async_recommended);

    if (useAsync) {
      return CF.startExportJob(type, format);
    }

    try {
      CF.setExportStatus('running', 'Processing');
      const res = await fetch(`/api/exports/${type}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ format, report_type: type }),
      });
      const ct = res.headers.get('content-type') || '';
      if (ct.includes('application/json')) {
        const data = await res.json();
        if (data.async && data.job) {
          CF.showExportProgress(true);
          return CF.pollExportJob(data.job.id, type);
        }
        if (!res.ok) throw new Error(data.message || 'Export failed');
      } else if (!res.ok) {
        throw new Error('Export failed');
      }
      const blob = await res.blob();
      const disposition = res.headers.get('Content-Disposition') || '';
      const match = disposition.match(/filename="?([^";]+)"?/i);
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = match ? match[1] : `commerceflow_${type}.${format}`;
      a.click();
      CF.setExportStatus('ready', 'Ready');
      CF.toast(`Exported ${type} report`, 'success');
    } catch (e) {
      CF.setExportStatus('failed', 'Failed');
      CF.toast(CF.parseApiError(e).split('\n')[0] || 'Export failed', 'error');
    }
  },
};
