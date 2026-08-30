document.addEventListener("DOMContentLoaded", async () => {
  const datasetId = requireDataset();
  if (!datasetId) return;

  const body = document.getElementById("insights-body");
  body.innerHTML = loadingBlock("Deriving insights from your Gold data…");

  try {
    const data = await Api.getInsights(datasetId);
    render(data);
  } catch (err) {
    body.innerHTML = errorBlock("Insights not available yet", err.message);
  }

  function severityIcon(sev) {
    return sev === "warning" ? "⚠" : sev === "positive" ? "▲" : "●";
  }

  // Convert dollar currency display to Indian Rupees.
  // This only changes presentation; the underlying numeric values remain unchanged.
  function formatInsightText(text) {
    if (text === null || text === undefined) return "";

    return String(text)
      .replace(/\$/g, "₹")
      .replace(/\bUSD\b/gi, "INR");
  }

  function render(data) {
    if (!data.insights.length) {
      body.innerHTML = emptyBlock(
        "Not enough mapped data for insights yet",
        "Insights need at least a sales trend, category, region, or profitability signal. Try mapping more optional fields.",
      );
      return;
    }

    const insightCards = data.insights.map(i => `
      <div class="card">
        <div class="flex gap-3 mb-3" style="align-items:flex-start;">
          ${statusBadge(i.severity)}
        </div>

        <div class="text-sm text-muted mb-2"
             style="text-transform:uppercase; font-size:0.6875rem; letter-spacing:0.04em; font-weight:650;">
          Metric
        </div>

        <div class="mono mb-4" style="font-size:0.9375rem;">
          ${escapeHtml(formatInsightText(i.metric))}
        </div>

        <div class="text-sm text-muted mb-2"
             style="text-transform:uppercase; font-size:0.6875rem; letter-spacing:0.04em; font-weight:650;">
          Insight
        </div>

        <div>
          ${escapeHtml(formatInsightText(i.insight))}
        </div>
      </div>
    `).join("");

    const recCards = data.recommendations.map(r => `
      <div class="card">
        <div class="flex-between mb-3">
          <div class="card-title">Recommendation</div>
          ${statusBadge(r.severity)}
        </div>

        <p>
          ${escapeHtml(formatInsightText(r.recommendation))}
        </p>

        <div class="text-sm text-muted mt-4"
             style="border-top:1px solid var(--border); padding-top: var(--sp-3);">
          ${escapeHtml(formatInsightText(r.disclaimer))}
        </div>
      </div>
    `).join("");

    body.innerHTML = `
      <h2 class="mb-4">Insights</h2>

      <div class="grid grid-2 mb-6">
        ${insightCards}
      </div>

      ${
        data.recommendations.length
          ? `
            <h2 class="mb-4">Recommended Actions</h2>
            <div class="grid grid-2">
              ${recCards}
            </div>
          `
          : ""
      }
    `;
  }
});