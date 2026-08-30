document.addEventListener("DOMContentLoaded", async () => {
  renderStageTracker("quality");
  const datasetId = requireDataset();
  if (!datasetId) return;

  const body = document.getElementById("quality-body");
  body.innerHTML = loadingBlock("Running data quality checks…");

  try {
    const report = await Api.getQuality(datasetId);
    render(report);
  } catch (err) {
    body.innerHTML = errorBlock("Couldn't compute data quality", err.message);
  }

  function scoreClass(score) {
    if (score >= 90) return "success";
    if (score >= 70) return "warning";
    return "critical";
  }

  function dimensionBar(label, value) {
    const cls = scoreClass(value);
    return `
      <div class="mb-4">
        <div class="flex-between text-sm mb-2">
          <span style="font-weight:600;">${label}</span>
          <span class="mono">${formatPercent(value)}</span>
        </div>
        <div class="progress-track">
          <div class="progress-fill" style="width:${Math.max(value, 2)}%; background: var(--${cls});"></div>
        </div>
      </div>
    `;
  }

  function render(report) {
    const cls = scoreClass(report.score_overall);
    const issueRows = report.issues
      .sort((a, b) => ({ critical: 0, warning: 1, info: 2 }[a.severity] - { critical: 0, warning: 1, info: 2 }[b.severity]))
      .map(i => `
        <tr>
          <td>${statusBadge(i.severity)}</td>
          <td class="mono">${escapeHtml(i.field || "—")}</td>
          <td>${escapeHtml(i.description)}</td>
          <td class="mono">${formatNumber(i.affected_rows)}</td>
        </tr>
      `).join("");

    body.innerHTML = `
      <div class="grid grid-2">
        <div class="card" style="display:flex; flex-direction:column; align-items:center; justify-content:center;">
          <div class="kpi-label mb-2">Data Quality Score</div>
          <div style="font-family: var(--font-mono); font-size: 3rem; font-weight: 700; color: var(--${cls});">
            ${report.score_overall.toFixed(1)}<span style="font-size:1.25rem; color:var(--slate-400);">/100</span>
          </div>
          <div class="text-sm text-muted mt-2">${formatNumber(report.row_count)} rows evaluated</div>
        </div>
        <div class="card">
          ${dimensionBar("Completeness", report.completeness)}
          ${dimensionBar("Uniqueness", report.uniqueness)}
          ${dimensionBar("Validity", report.validity)}
          ${dimensionBar("Consistency", report.consistency)}
          ${dimensionBar("Schema Match", report.schema_match)}
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">Data quality issues</div>
            <div class="card-desc">${report.issues.length} issue(s) found — dirty data is reported, not rejected at this stage</div>
          </div>
          <a class="btn btn-secondary btn-sm" href="${Api.downloadUrl(datasetId, "quality-report")}">Download Report</a>
        </div>
        ${report.issues.length ? `
          <div class="table-wrap">
            <table>
              <thead><tr><th>Severity</th><th>Field</th><th>Description</th><th>Affected Rows</th></tr></thead>
              <tbody>${issueRows}</tbody>
            </table>
          </div>
        ` : emptyBlock("No issues found", "This dataset passed every quality check Nexus runs.")}
      </div>

      <div class="card flex-between">
        <div class="text-sm text-muted">Ready to clean, transform, and build analytics from this dataset.</div>
        <a class="btn btn-primary" href="processing.html">Continue to Processing →</a>
      </div>
    `;
  }
});
