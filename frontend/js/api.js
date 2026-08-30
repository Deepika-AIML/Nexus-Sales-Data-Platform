/*
  Nexus API client.

  Local Docker:
    Frontend: http://localhost:8080
    Backend:  http://localhost:8000

  Render:
    Frontend and backend are deployed separately.
    Set the Render backend URL below after the backend is deployed.
*/

const LOCAL_API_BASE = `${window.location.protocol}//${window.location.hostname}:8000`;

// -----------------------------------------------------------------------------
// Render backend URL
// -----------------------------------------------------------------------------
// We will replace this with your actual Render backend URL after deployment.
//
// Example:
// const RENDER_API_BASE = "https://nexus-backend-xxxx.onrender.com";
//
const RENDER_API_BASE = "";

// -----------------------------------------------------------------------------
// Select API base automatically
// -----------------------------------------------------------------------------

const API_BASE = RENDER_API_BASE
  ? RENDER_API_BASE.replace(/\/$/, "")
  : LOCAL_API_BASE;


// -----------------------------------------------------------------------------
// API request helper
// -----------------------------------------------------------------------------

async function apiRequest(path, options = {}) {
  let response;

  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers:
        options.body instanceof FormData
          ? undefined
          : { "Content-Type": "application/json" },
      ...options,
    });
  } catch (networkErr) {
    throw new Error(
      "Could not reach the Nexus backend. Please check that the backend is running."
    );
  }

  if (!response.ok) {
    let detail = `Request failed (${response.status})`;

    try {
      const body = await response.json();

      if (body && body.detail) {
        detail = body.detail;
      }
    } catch (_) {
      // Non-JSON error response.
    }

    throw new Error(detail);
  }

  const contentType =
    response.headers.get("content-type") || "";

  if (contentType.includes("application/json")) {
    return response.json();
  }

  return response;
}


// -----------------------------------------------------------------------------
// Nexus API
// -----------------------------------------------------------------------------

const Api = {

  upload(file) {
    const form = new FormData();

    form.append("file", file);

    return apiRequest("/api/upload", {
      method: "POST",
      body: form,
    });
  },


  getProfile(datasetId) {
    return apiRequest(`/api/profile/${datasetId}`);
  },


  suggestMapping(datasetId) {
    return apiRequest(
      `/api/mapping/${datasetId}`,
      {
        method: "POST",
      }
    );
  },


  getMapping(datasetId) {
    return apiRequest(
      `/api/mapping/${datasetId}`
    );
  },


  confirmMapping(datasetId, mappings) {
    return apiRequest(
      `/api/mapping/${datasetId}/confirm`,
      {
        method: "POST",
        body: JSON.stringify({
          mappings,
        }),
      }
    );
  },


  getQuality(datasetId) {
    return apiRequest(
      `/api/quality/${datasetId}`
    );
  },


  startProcessing(
    datasetId,
    writeToMysql = true
  ) {
    return apiRequest(
      `/api/process/${datasetId}`,
      {
        method: "POST",
        body: JSON.stringify({
          write_to_mysql: writeToMysql,
        }),
      }
    );
  },


  getResults(datasetId) {
    return apiRequest(
      `/api/results/${datasetId}`
    );
  },


  getAnalytics(datasetId) {
    return apiRequest(
      `/api/analytics/${datasetId}`
    );
  },


  getInsights(datasetId) {
    return apiRequest(
      `/api/insights/${datasetId}`
    );
  },


  getHistory() {
    return apiRequest(
      `/api/history`
    );
  },


  downloadUrl(datasetId, kind) {
    // kind:
    // 'clean'
    // 'rejected'
    // 'quality-report'
    // 'mapping-report'

    return `${API_BASE}/api/download/${datasetId}/${kind}`;
  },


  health() {
    return apiRequest(
      `/api/health`
    );
  },

};