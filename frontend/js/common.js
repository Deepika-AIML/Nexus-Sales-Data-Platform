/* Shared UI helpers used by every page. */

const NAV_ITEMS = [
  { id: "overview", label: "Overview", href: "index.html" },
  { id: "upload", label: "Upload Dataset", href: "upload.html" },
  { id: "mapping", label: "Data Mapping", href: "mapping.html" },
  { id: "quality", label: "Data Quality", href: "quality.html" },
  { id: "processing", label: "Processing", href: "processing.html" },
  { id: "analytics", label: "Analytics", href: "analytics.html" },
  { id: "insights", label: "Insights", href: "insights.html" },
  { id: "history", label: "History", href: "history.html" },
  { id: "settings", label: "Settings", href: "settings.html" },
];

function renderSidebar(activeId) {
  const mount = document.getElementById("sidebar-mount");
  if (!mount) return;
  const items = NAV_ITEMS.map(item => `
    <a class="nav-item ${item.id === activeId ? "active" : ""}" href="${item.href}">
      <span class="dot"></span><span>${item.label}</span>
    </a>
  `).join("");

  mount.innerHTML = `
    <div class="sidebar-brand">
      <div class="brand-mark"></div>
      <div>
        <div class="brand-name">NEXUS</div>
        <div class="brand-sub">Sales Data Platform</div>
      </div>
    </div>
    <nav class="sidebar-nav">${items}</nav>
    <div class="sidebar-footer">
      <span class="env-badge"><span class="layer-stack"><span></span><span></span><span></span></span> Bronze &middot; Silver &middot; Gold</span>
    </div>
  `;
}

function getDatasetId() {
  return localStorage.getItem("nexus_dataset_id");
}
function setDatasetId(id) {
  localStorage.setItem("nexus_dataset_id", id);
}
function getDatasetName() {
  return localStorage.getItem("nexus_dataset_name") || "";
}
function setDatasetName(name) {
  localStorage.setItem("nexus_dataset_name", name);
}

/** Redirects to the Upload page with a message if no dataset is active yet.
 *  Returns the dataset_id if one exists (so callers can proceed inline). */
function requireDataset() {
  const id = getDatasetId();
  if (!id) {
    window.location.href = "upload.html?required=1";
    return null;
  }
  return id;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str === null || str === undefined ? "" : String(str);
  return div.innerHTML;
}

function formatBytes(bytes) {
  if (bytes === null || bytes === undefined) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let val = bytes, i = 0;
  while (val >= 1024 && i < units.length - 1) { val /= 1024; i++; }
  return `${val.toFixed(val < 10 && i > 0 ? 1 : 0)} ${units[i]}`;
}

function formatNumber(n) {
  if (n === null || n === undefined) return "—";
  return Number(n).toLocaleString("en-US");
}

function formatCurrency(n) {
  if (n === null || n === undefined) return "—";
  return Number(n).toLocaleString("en-US", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
}

function formatPercent(n, digits = 1) {
  if (n === null || n === undefined) return "—";
  return `${Number(n).toFixed(digits)}%`;
}

function formatDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" });
  } catch (_) { return iso; }
}

const STATUS_BADGE_MAP = {
  uploaded: "info", profiled: "info", mapping_review: "warning", mapped: "silver",
  quality_checked: "silver", processing: "gold", processed: "success", failed: "critical",
  auto_mapped: "success", review: "warning", unmapped: "neutral",
  manual: "info", confirmed: "success", removed: "neutral",
  critical: "critical", warning: "warning", info: "info",
  queued: "neutral", completed: "success",
  positive: "success", neutral: "neutral",
};

function statusBadge(status) {
  const cls = STATUS_BADGE_MAP[status] || "neutral";
  const label = String(status || "").replace(/_/g, " ");
  return `<span class="badge badge-${cls}">${escapeHtml(label)}</span>`;
}

function layerStackGlyph(loading = false) {
  return `<span class="layer-stack ${loading ? "loading" : ""}"><span></span><span></span><span></span></span>`;
}

const PIPELINE_STAGES = [
  { id: "upload", label: "Upload" },
  { id: "mapping", label: "Mapping" },
  { id: "quality", label: "Quality" },
  { id: "processing", label: "Processing" },
  { id: "results", label: "Results" },
];

function renderStageTracker(currentId) {
  const el = document.getElementById("stage-tracker");
  if (!el) return;
  const currentIdx = PIPELINE_STAGES.findIndex(s => s.id === currentId);
  el.innerHTML = PIPELINE_STAGES.map((s, i) => {
    const state = i < currentIdx ? "done" : i === currentIdx ? "current" : "";
    const glyph = i < currentIdx ? "✓" : i + 1;
    const line = i > 0 ? `<span class="stage-line ${i <= currentIdx ? "done" : ""}"></span>` : "";
    return `${line}<div class="stage-step ${state}"><span class="stage-dot">${glyph}</span><span class="stage-label">${s.label}</span></div>`;
  }).join("");
}

function loadingBlock(message = "Loading…") {
  return `<div class="loading-state">${layerStackGlyph(true)}<div>${escapeHtml(message)}</div></div>`;
}

function errorBlock(title, message) {
  return `<div class="error-state"><h3>${escapeHtml(title)}</h3><p>${escapeHtml(message)}</p></div>`;
}

function emptyBlock(title, message, actionHtml = "") {
  return `<div class="empty-state"><h3>${escapeHtml(title)}</h3><p>${escapeHtml(message)}</p>${actionHtml}</div>`;
}

let toastTimer = null;
function showToast(message, type = "info") {
  let el = document.getElementById("nexus-toast");
  if (!el) {
    el = document.createElement("div");
    el.id = "nexus-toast";
    el.style.position = "fixed";
    el.style.bottom = "24px";
    el.style.right = "24px";
    el.style.zIndex = "999";
    el.style.maxWidth = "360px";
    el.style.boxShadow = "var(--shadow-pop)";
    el.style.borderRadius = "10px";
    document.body.appendChild(el);
  }
  const cls = type === "error" ? "alert-critical" : type === "success" ? "alert-success" : "alert-info";
  el.innerHTML = `<div class="alert ${cls}">${escapeHtml(message)}</div>`;
  el.style.display = "block";
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.style.display = "none"; }, 5000);
}

document.addEventListener("DOMContentLoaded", () => {
  const active = document.body.getAttribute("data-nav");
  if (active) renderSidebar(active);
});

/* ===================== LIGHTWEIGHT SVG CHARTS (no external library) ===================== */

function renderBarChart(items, { labelKey, valueKey, width = 640, barHeight = 28, gap = 10, color = "var(--accent-600)", valueFormatter = formatCurrency }) {
  if (!items.length) return "";
  const max = Math.max(...items.map(i => i[valueKey]), 1);
  const labelW = 150;
  const chartW = width - labelW - 70;
  const rows = items.map((item, idx) => {
    const w = Math.max((item[valueKey] / max) * chartW, 2);
    const y = idx * (barHeight + gap);
    return `
      <text x="0" y="${y + barHeight / 2 + 4}" font-size="12" fill="var(--slate-600)" class="mono">${escapeHtml(String(item[labelKey]).slice(0, 20))}</text>
      <rect x="${labelW}" y="${y}" width="${w}" height="${barHeight}" rx="4" fill="${color}"></rect>
      <text x="${labelW + w + 8}" y="${y + barHeight / 2 + 4}" font-size="12" fill="var(--ink-900)" class="mono">${escapeHtml(valueFormatter(item[valueKey]))}</text>
    `;
  }).join("");
  const height = items.length * (barHeight + gap);
  return `<svg viewBox="0 0 ${width} ${height}" width="100%" height="${height}" role="img" aria-label="Bar chart">${rows}</svg>`;
}

function renderLineChart(points, { xKey, yKey, width = 640, height = 220, color = "var(--accent-600)", valueFormatter = formatCurrency }) {
  if (!points || points.length < 2) return `<div class="text-sm text-muted">Not enough data points to draw a trend line.</div>`;
  const pad = 36;
  const maxY = Math.max(...points.map(p => p[yKey]), 1);
  const minY = Math.min(...points.map(p => p[yKey]), 0);
  const stepX = (width - pad * 2) / (points.length - 1);
  const scaleY = (v) => height - pad - ((v - minY) / (maxY - minY || 1)) * (height - pad * 2);

  const coords = points.map((p, i) => [pad + i * stepX, scaleY(p[yKey])]);
  const path = coords.map((c, i) => `${i === 0 ? "M" : "L"}${c[0].toFixed(1)},${c[1].toFixed(1)}`).join(" ");
  const areaPath = `${path} L${coords[coords.length - 1][0]},${height - pad} L${coords[0][0]},${height - pad} Z`;
  const dots = coords.map((c, i) => `<circle cx="${c[0]}" cy="${c[1]}" r="3" fill="${color}"><title>${escapeHtml(String(points[i][xKey]))}: ${escapeHtml(valueFormatter(points[i][yKey]))}</title></circle>`).join("");
  const labels = points.map((p, i) => `<text x="${coords[i][0]}" y="${height - 10}" font-size="10" fill="var(--slate-500)" text-anchor="middle">${escapeHtml(String(p[xKey]))}</text>`).join("");

  return `
    <svg viewBox="0 0 ${width} ${height}" width="100%" height="${height}" role="img" aria-label="Trend line chart">
      <path d="${areaPath}" fill="var(--accent-100)" opacity="0.6"></path>
      <path d="${path}" fill="none" stroke="${color}" stroke-width="2.5"></path>
      ${dots}
      ${labels}
    </svg>
  `;
}
