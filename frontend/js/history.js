document.addEventListener("DOMContentLoaded", async () => {
  const body = document.getElementById("history-body");
  body.innerHTML = loadingBlock("Loading processing history…");

  try {
    const data = await Api.getHistory();
    render(data.items);
  } catch (err) {
    body.innerHTML = errorBlock("Couldn't load history", err.message);
  }

  function render(items) {
    if (!items.length) {
      body.innerHTML = `<div class="card">${emptyBlock(
        "No datasets yet",
        "Upload your first sales CSV to see it appear here.",
        `<a class="btn btn-primary mt-4" href="upload.html">Upload Dataset</a>`,
      )}</div>`;
      return;
    }

    const rows = items.map(d => `
      <tr style="cursor:pointer;" data-id="${d.dataset_id}" data-name="${escapeHtml(d.original_filename)}">
        <td>${escapeHtml(d.original_filename)}</td>
        <td class="text-sm text-muted">${formatDate(d.uploaded_at)}</td>
        <td class="mono">${formatNumber(d.row_count)}</td>
        <td class="mono">${formatNumber(d.column_count)}</td>
        <td class="mono">${d.quality_score !== null ? d.quality_score.toFixed(1) : "—"}</td>
        <td>${statusBadge(d.status)}</td>
        <td><button class="btn btn-secondary btn-sm open-btn" data-id="${d.dataset_id}" data-name="${escapeHtml(d.original_filename)}">Open →</button></td>
      </tr>
    `).join("");

    body.innerHTML = `
      <div class="card">
        <div class="table-wrap">
          <table>
            <thead><tr><th>Dataset</th><th>Uploaded</th><th>Rows</th><th>Columns</th><th>Quality</th><th>Status</th><th></th></tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      </div>
    `;

    body.querySelectorAll(".open-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        setDatasetId(btn.dataset.id);
        setDatasetName(btn.dataset.name);
        window.location.href = "mapping.html";
      });
    });
  }
});
