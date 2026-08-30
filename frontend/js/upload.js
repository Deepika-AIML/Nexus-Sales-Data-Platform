document.addEventListener("DOMContentLoaded", () => {
  renderStageTracker("upload");

  const params = new URLSearchParams(window.location.search);
  if (params.get("required") === "1") {
    document.getElementById("required-banner").classList.remove("hidden");
  }

  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("file-input");
  const fileInfo = document.getElementById("file-info");
  const fileName = document.getElementById("file-name");
  const fileSize = document.getElementById("file-size");
  const uploadBtn = document.getElementById("upload-btn");
  const statusEl = document.getElementById("upload-status");

  let selectedFile = null;

  dropzone.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("dragover"); });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length) selectFile(e.dataTransfer.files[0]);
  });
  fileInput.addEventListener("change", () => {
    if (fileInput.files.length) selectFile(fileInput.files[0]);
  });

  function selectFile(file) {
    selectedFile = file;
    fileName.textContent = file.name;
    fileSize.textContent = formatBytes(file.size);
    fileInfo.classList.remove("hidden");
    statusEl.innerHTML = "";

    if (!file.name.toLowerCase().endsWith(".csv")) {
      statusEl.innerHTML = `<div class="alert alert-critical mt-2">Unsupported file type. Please upload a CSV file.</div>`;
      uploadBtn.disabled = true;
    } else if (file.size > 25 * 1024 * 1024) {
      statusEl.innerHTML = `<div class="alert alert-critical mt-2">File exceeds the 25 MB upload limit.</div>`;
      uploadBtn.disabled = true;
    } else {
      uploadBtn.disabled = false;
    }
  }

  uploadBtn.addEventListener("click", async () => {
    if (!selectedFile) return;
    uploadBtn.disabled = true;
    uploadBtn.textContent = "Uploading…";
    statusEl.innerHTML = loadingBlock("Validating and uploading your file…");

    try {
      const result = await Api.upload(selectedFile);
      setDatasetId(result.dataset_id);
      setDatasetName(result.original_filename);
      statusEl.innerHTML = `<div class="alert alert-success">${escapeHtml(result.message)}</div>`;
      await loadProfile(result.dataset_id);
    } catch (err) {
      statusEl.innerHTML = `<div class="alert alert-critical">${escapeHtml(err.message)}</div>`;
      uploadBtn.disabled = false;
      uploadBtn.textContent = "Upload";
    }
  });

  async function loadProfile(datasetId) {
    const card = document.getElementById("profile-card");
    const body = document.getElementById("profile-body");
    card.classList.remove("hidden");
    body.innerHTML = loadingBlock("Profiling dataset…");

    try {
      const profile = await Api.getProfile(datasetId);
      const rows = profile.columns.map(c => `
        <tr>
          <td class="mono">${escapeHtml(c.name)}</td>
          <td>${statusBadge(c.inferred_type === "numeric" ? "success" : c.inferred_type === "date" ? "info" : "neutral")}${escapeHtml(c.inferred_type)}</td>
          <td>${formatNumber(c.unique_count)}</td>
          <td>${formatPercent(c.null_pct)}</td>
          <td class="text-sm text-muted">${c.sample_values.map(v => escapeHtml(v)).slice(0, 3).join(", ")}</td>
        </tr>
      `).join("");

      body.innerHTML = `
        <div class="grid grid-4 mb-6">
          <div class="kpi"><div class="kpi-label">Rows</div><div class="kpi-value">${formatNumber(profile.row_count)}</div></div>
          <div class="kpi"><div class="kpi-label">Columns</div><div class="kpi-value">${formatNumber(profile.column_count)}</div></div>
          <div class="kpi"><div class="kpi-label">File Size</div><div class="kpi-value">${formatBytes(profile.file_size_bytes)}</div></div>
          <div class="kpi"><div class="kpi-label">Encoding</div><div class="kpi-value" style="font-size:1.1rem;">${escapeHtml(profile.detected_encoding)}</div></div>
        </div>
        ${profile.duplicate_row_count > 0 ? `<div class="alert alert-warning mb-4">${profile.duplicate_row_count} fully duplicate row(s) detected in the raw file — this will be reviewed during Data Quality.</div>` : ""}
        <div class="table-wrap">
          <table>
            <thead><tr><th>Column</th><th>Inferred Type</th><th>Unique</th><th>Null %</th><th>Sample Values</th></tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      `;
    } catch (err) {
      body.innerHTML = errorBlock("Couldn't load profile", err.message);
    }
  }

  // If a dataset is already active (e.g. returning to this page), show its profile.
  const existing = getDatasetId();
  if (existing && !params.get("required")) {
    loadProfile(existing);
  }
});
