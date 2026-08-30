document.addEventListener("DOMContentLoaded", () => {
  renderStageTracker("mapping");
  const datasetId = requireDataset();
  if (!datasetId) return;

  document.getElementById("dataset-sub").textContent = `Reviewing: ${getDatasetName() || datasetId}`;

  const body = document.getElementById("mapping-body");
  const summaryEl = document.getElementById("mapping-summary");
  const conflictsBanner = document.getElementById("conflicts-banner");
  const confirmBtn = document.getElementById("confirm-btn");
  const confirmStatus = document.getElementById("confirm-status");
  const regenerateBtn = document.getElementById("regenerate-btn");

  let fieldMeta = { core: [], recommended: [], optional: [] };

  async function load(forceRegenerate) {
    body.innerHTML = loadingBlock("Analyzing your columns…");
    conflictsBanner.innerHTML = "";
    try {
      let data = forceRegenerate ? null : await Api.getMapping(datasetId);
      if (!data || !data.suggestions || data.suggestions.length === 0) {
        data = await Api.suggestMapping(datasetId);
      }
      fieldMeta = { core: data.core_fields, recommended: data.recommended_fields, optional: data.optional_fields };
      renderConflicts(data.conflicts);
      renderTable(data.suggestions);
    } catch (err) {
      body.innerHTML = errorBlock("Couldn't load column mapping", err.message);
    }
  }

  function renderConflicts(conflicts) {
    if (!conflicts || conflicts.length === 0) return;
    conflictsBanner.innerHTML = conflicts.map(c => `
      <div class="alert alert-warning mb-4">${escapeHtml(c.message)}</div>
    `).join("");
  }

  function fieldOptions(selected) {
    const groups = [
      ["Core (required)", fieldMeta.core],
      ["Recommended", fieldMeta.recommended],
      ["Optional", fieldMeta.optional],
    ];
    let html = `<option value="" ${!selected ? "selected" : ""}>— Unmapped —</option>`;
    for (const [label, fields] of groups) {
      if (!fields || fields.length === 0) continue;
      html += `<optgroup label="${label}">`;
      html += fields.map(f => `<option value="${f}" ${f === selected ? "selected" : ""}>${f}</option>`).join("");
      html += `</optgroup>`;
    }
    return html;
  }

  function renderTable(suggestions) {
    if (!suggestions.length) {
      body.innerHTML = emptyBlock("No columns found", "This dataset doesn't appear to have any columns.");
      return;
    }
    const rows = suggestions.map(s => `
      <tr data-source="${escapeHtml(s.source_column)}">
        <td>
          <div class="mono" style="font-weight:600;">${escapeHtml(s.source_column)}</div>
          ${s.sample_values && s.sample_values.length ? `<div class="text-sm text-muted">${s.sample_values.slice(0, 3).map(escapeHtml).join(", ")}</div>` : ""}
        </td>
        <td><select class="field-select" data-source="${escapeHtml(s.source_column)}">${fieldOptions(s.best_field)}</select></td>
        <td class="mono">${s.confidence ? s.confidence.toFixed(1) + "%" : "—"}</td>
        <td>${statusBadge(s.status)}</td>
      </tr>
    `).join("");

    body.innerHTML = `
      <div class="table-wrap">
        <table>
          <thead><tr><th>Source Column</th><th>Nexus Field</th><th>Confidence</th><th>Status</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    `;
    updateSummary();
    body.querySelectorAll(".field-select").forEach(sel => sel.addEventListener("change", updateSummary));
  }

  function updateSummary() {
    const selects = Array.from(document.querySelectorAll(".field-select"));
    const mappedCount = selects.filter(s => s.value).length;
    summaryEl.textContent = `${mappedCount} of ${selects.length} source column(s) mapped.`;
  }

  confirmBtn.addEventListener("click", async () => {
    const selects = Array.from(document.querySelectorAll(".field-select"));
    const mappings = selects.map(s => ({ source_column: s.dataset.source, canonical_field: s.value || null }));

    confirmBtn.disabled = true;
    confirmStatus.innerHTML = loadingBlock("Confirming mapping…");

    try {
      const result = await Api.confirmMapping(datasetId, mappings);
      if (result.can_proceed) {
        let optionalNote = "";
        if (result.missing_optional_fields.length) {
          optionalNote = `<div class="alert alert-info mt-2">Optional attributes unavailable: ${result.missing_optional_fields.map(escapeHtml).join(", ")}. Some analytics will be limited.</div>`;
        }
        confirmStatus.innerHTML = `
          <div class="alert alert-success">${escapeHtml(result.message)}</div>
          ${optionalNote}
          <a class="btn btn-primary mt-4" href="quality.html">Continue to Data Quality →</a>
        `;
      } else {
        confirmStatus.innerHTML = `<div class="alert alert-critical">${escapeHtml(result.message)} Please map a source column to it, or upload a different dataset.</div>`;
      }
    } catch (err) {
      confirmStatus.innerHTML = `<div class="alert alert-critical">${escapeHtml(err.message)}</div>`;
    } finally {
      confirmBtn.disabled = false;
    }
  });

  regenerateBtn.addEventListener("click", () => load(true));

  load(false);
});
