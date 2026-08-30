document.addEventListener("DOMContentLoaded", async () => {
  const statusEl = document.getElementById("backend-status");
  statusEl.innerHTML = loadingBlock("Checking backend…");
  try {
    await Api.health();
    statusEl.innerHTML = `<div class="alert alert-success">Backend reachable at ${window.location.protocol}//${window.location.hostname}:8000</div>`;
  } catch (err) {
    statusEl.innerHTML = `<div class="alert alert-critical">${escapeHtml(err.message)}</div>`;
  }

  const sessionEl = document.getElementById("session-info");
  const id = getDatasetId();
  sessionEl.innerHTML = id
    ? `Active dataset: <span class="mono">${escapeHtml(getDatasetName() || id)}</span> <span class="mono text-muted">(${escapeHtml(id)})</span>`
    : `No dataset is currently active.`;

  document.getElementById("clear-session-btn").addEventListener("click", () => {
    localStorage.removeItem("nexus_dataset_id");
    localStorage.removeItem("nexus_dataset_name");
    showToast("Active dataset cleared.", "success");
    sessionEl.textContent = "No dataset is currently active.";
  });
});
