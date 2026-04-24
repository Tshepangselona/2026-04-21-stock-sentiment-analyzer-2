const analyzeBtn = document.getElementById("analyzeBtn");
const fetchBtn = document.getElementById("fetchBtn");
const headlineInput = document.getElementById("headlineInput");
const providerSelect = document.getElementById("providerSelect");
const tickerInput = document.getElementById("tickerInput");
const queryInput = document.getElementById("queryInput");
const limitInput = document.getElementById("limitInput");
const summaryCards = document.getElementById("summaryCards");
const headlineResults = document.getElementById("headlineResults");
const statusLine = document.getElementById("statusLine");

analyzeBtn.addEventListener("click", async () => {
  const headlines = parseManualInput(headlineInput.value);
  if (!headlines.length) {
    renderError("Add at least one valid headline first.");
    return;
  }
  await submit("/api/analyze", { headlines }, "Manual analysis complete.");
});

fetchBtn.addEventListener("click", async () => {
  await submit(
    "/api/fetch",
    {
      provider: providerSelect.value,
      ticker: tickerInput.value,
      query: queryInput.value,
      limit: Number(limitInput.value || 5),
    },
    `Live fetch complete from ${providerSelect.value}.`
  );
});

function parseManualInput(rawText) {
  return rawText
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const parts = line.split("|").map((part) => part.trim());
      if (parts.length >= 3) {
        return { ticker: parts[0], source: parts[1], headline: parts.slice(2).join(" | ") };
      }
      if (parts.length === 2) {
        return { ticker: parts[0], headline: parts[1] };
      }
      return { headline: line };
    });
}

async function submit(url, payload, successMessage) {
  setStatus("Working on it...");
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Request failed.");
    }
    renderResult(data);
    setStatus(successMessage);
  } catch (error) {
    renderError(error.message);
  }
}

function renderResult(result) {
  summaryCards.innerHTML = [
    card("Overall", `${result.overall_label} ${signed(result.average_score)}`),
    card("Confidence", result.confidence.toFixed(2)),
    card("Headline Count", String(result.headline_count)),
    card("Breakdown", `${result.bullish_count}/${result.bearish_count}/${result.neutral_count}`),
  ].join("");

  headlineResults.innerHTML = result.headlines
    .map(
      (item) => `
        <article class="headline-card">
          <div class="headline-top">
            <div>
              <h4>${escapeHtml(item.headline)}</h4>
              <div class="meta">
                Score ${signed(item.score)}
                ${item.ticker ? ` | Ticker ${escapeHtml(item.ticker)}` : ""}
                ${item.source ? ` | Source ${escapeHtml(item.source)}` : ""}
              </div>
            </div>
            <span class="pill ${item.label.replace(/\s+/g, " ")}">${escapeHtml(item.label)}</span>
          </div>
          <div class="drivers">
            ${renderDrivers(item.matched_positive_terms, "positive")}
            ${renderDrivers(item.matched_negative_terms, "negative")}
          </div>
        </article>
      `
    )
    .join("");
}

function renderDrivers(items, tone) {
  if (!items.length) {
    return "";
  }
  return items.map((item) => `<span class="${tone}">${escapeHtml(item)}</span>`).join("");
}

function renderError(message) {
  summaryCards.innerHTML = "";
  headlineResults.innerHTML = `<div class="empty">${escapeHtml(message)}</div>`;
  setStatus("Something needs attention.");
}

function setStatus(message) {
  statusLine.textContent = message;
}

function card(label, value) {
  return `<div class="summary-card"><h3>${escapeHtml(label)}</h3><strong>${escapeHtml(value)}</strong></div>`;
}

function signed(value) {
  return `${value >= 0 ? "+" : ""}${Number(value).toFixed(2)}`;
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
