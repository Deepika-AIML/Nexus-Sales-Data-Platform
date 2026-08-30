const JOB_STAGES = [
  "queued", "uploading", "profiling", "mapping", "validating",
  "cleaning", "transforming", "building_analytics_model", "generating_insights", "completed",
];
const STAGE_LABELS = {
  queued: "Queued", uploading: "Uploading", profiling: "Profiling", mapping: "Mapping",
  validating: "Validating", cleaning: "Cleaning", transforming: "Transforming",
  building_analytics_model: "Building analytics model", generating_insights: "Generating insights",
  completed: "Completed",
};

document.addEventListener("DOMContentLoaded", () => {
  renderStageTracker("processing");
  const datasetId = requireDataset();
  if (!datasetId) return;

  const body = document.getElementById("processing-body");
  let pollTimer = null;

  function renderStageList(currentStatus) {
    const currentIdx = JOB_STAGES.indexOf(currentStatus);
    return `
      <div class="flex-col gap-3">
        ${JOB_STAGES.map((s, i) => {
          const state = currentStatus === "failed" ? "" : i < currentIdx ? "done" : i === currentIdx ? "current" : "";
          const icon = state === "done" ? "✓" : i + 1;
          return `
            <div class="flex gap-3" style="align-items:center;">
              <span class="stage-dot" style="${state === "done" ? "background:var(--success-bg); color:var(--success);" : state === "current" ? "background:var(--accent-600); color:#fff;" : ""}">${icon}</span>
              <span style="${state ? "font-weight:600;" : "color:var(--slate-400);"}">${STAGE_LABELS[s]}</span>
            </div>
          `;
        }).join("")}
      </div>
    `;
  }

  function renderIdle() {
    body.innerHTML = `
      <div class="card" style="text-align:center; padding: var(--sp-9);">
        ${layerStackGlyph(false)}
        <h3 class="mt-4 mb-2">Ready to process this dataset</h3>
        <p class="text-sm text-muted" style="max-width:480px; margin:0 auto var(--sp-6);">
          Nexus will ingest your file into Bronze, clean and standardize it into Silver, and build an
          analytics-ready Gold star schema in MySQL — all via PySpark.
        </p>
        <button class="btn btn-primary" id="start-btn">Start Processing</button>
        <div id="start-error" class="mt-4"></div>
      </div>
    `;
    document.getElementById("start-btn").addEventListener("click", startProcessing);
  }

  async function startProcessing() {
    const btn = document.getElementById("start-btn");
    const errEl = document.getElementById("start-error");
    btn.disabled = true;
    btn.textContent = "Starting…";
    try {
      await Api.startProcessing(datasetId, true);
      renderRunning("queued");
      poll();
    } catch (err) {
      errEl.innerHTML = `<div class="alert alert-critical">${escapeHtml(err.message)}</div>`;
      btn.disabled = false;
      btn.textContent = "Start Processing";
    }
  }

  function renderRunning(status) {
    body.innerHTML = `
      <div class="card">
        <div class="flex gap-4" style="align-items:center; margin-bottom: var(--sp-6);">
          ${layerStackGlyph(true)}
          <div>
            <div style="font-weight:650;">Processing in progress…</div>
            <div class="text-sm text-muted">This runs Bronze → Silver → Gold via PySpark and loads results into MySQL.</div>
          </div>
        </div>
        ${renderStageList(status)}
      </div>
    `;
  }

  function renderCompleted(job) {
    body.innerHTML = `
      <div class="alert alert-success mb-6">Processing completed in ${job.duration_seconds ?? "—"}s.</div>
      <div class="grid grid-3 mb-6">
        <div class="card kpi"><div class="kpi-label">Input Rows</div><div class="kpi-value">${formatNumber(job.input_rows)}</div></div>
        <div class="card kpi"><div class="kpi-label">Clean Rows</div><div class="kpi-value" style="color:var(--success);">${formatNumber(job.clean_rows)}</div></div>
        <div class="card kpi"><div class="kpi-label">Rejected Rows</div><div class="kpi-value" style="color:var(--critical);">${formatNumber(job.rejected_rows)}</div></div>
      </div>
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">Downloads</div>
            <div class="card-desc">Your original upload was never modified — these are pipeline outputs.</div>
          </div>
        </div>
        <div class="flex gap-3" style="flex-wrap:wrap;">
          <a class="btn btn-secondary" href="${Api.downloadUrl(datasetId, "clean")}">Download Clean Dataset</a>
          <a class="btn btn-secondary" href="${Api.downloadUrl(datasetId, "rejected")}">Download Rejected Records</a>
          <a class="btn btn-secondary" href="${Api.downloadUrl(datasetId, "mapping-report")}">Download Mapping Report</a>
          <a class="btn btn-secondary" href="${Api.downloadUrl(datasetId, "quality-report")}">Download Quality Report</a>
        </div>
      </div>
      <div class="card flex-between">
        <div class="text-sm text-muted">Your Gold analytics model is ready in MySQL.</div>
        <a class="btn btn-primary" href="analytics.html">Continue to Analytics →</a>
      </div>
    `;
  }

  function renderFailed(job) {
    body.innerHTML = `
      <div class="card" style="text-align:center; padding: var(--sp-8);">
        <div class="alert alert-critical mb-4" style="display:inline-flex;">${escapeHtml(job.error_message || "Processing could not be completed. Your original dataset remains unchanged.")}</div>
        <div><button class="btn btn-primary mt-4" id="retry-btn">Try Again</button></div>
      </div>
    `;
    document.getElementById("retry-btn").addEventListener("click", renderIdle);
  }

  async function poll() {
    clearTimeout(pollTimer);
    try {
      const job = await Api.getResults(datasetId);
      if (job.status === "completed") {
        renderCompleted(job);
        return;
      }
      if (job.status === "failed") {
        renderFailed(job);
        return;
      }
      renderRunning(job.status);
      pollTimer = setTimeout(poll, 1500);
    } catch (err) {
      // No job yet, or a transient error — fall back to idle state.
      renderIdle();
    }
  }

  poll();
});
