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
const distributionBars = document.getElementById("distributionBars");
const signalCards = document.getElementById("signalCards");
const metaBar = document.getElementById("metaBar");
const filterChips = Array.from(document.querySelectorAll(".filter-chip"));
const presetButtons = Array.from(document.querySelectorAll("[data-preset]"));
const livePresetButtons = Array.from(document.querySelectorAll("[data-live]"));

let currentResult = null;
let currentFilter = "all";

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

filterChips.forEach((chip) => {
  chip.addEventListener("click", () => {
    currentFilter = chip.dataset.filter || "all";
    filterChips.forEach((item) => item.classList.toggle("is-active", item === chip));
    if (currentResult) {
      renderHeadlineCards(currentResult);
    }
  });
});

presetButtons.forEach((button) => {
  button.addEventListener("click", () => {
    headlineInput.value = manualPresets[button.dataset.preset] || headlineInput.value;
    setStatus("Preset loaded. Analyze when ready.");
  });
});

livePresetButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const preset = livePresets[button.dataset.live];
    if (!preset) {
      return;
    }
    providerSelect.value = preset.provider;
    tickerInput.value = preset.ticker || "";
    queryInput.value = preset.query || "";
    limitInput.value = preset.limit;
    setStatus("Live preset loaded. Fetch when ready.");
  });
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
  currentResult = result;
  summaryCards.innerHTML = [
    card("Overall", `${result.overall_label} ${signed(result.average_score)}`),
    card("Confidence", result.confidence.toFixed(2)),
    card("Headline Count", String(result.headline_count)),
    card("Breakdown", `${result.bullish_count}/${result.bearish_count}/${result.neutral_count}`),
  ].join("");
  renderMeta(result.meta || {});
  renderDistribution(result);
  renderSignals(result);
  renderHeadlineCards(result);
}

function renderDrivers(items, tone) {
  if (!items.length) {
    return "";
  }
  return items.map((item) => `<span class="${tone}">${escapeHtml(item)}</span>`).join("");
}

function renderHeadlineCards(result) {
  const visible = result.headlines.filter(matchesCurrentFilter);
  if (!visible.length) {
    headlineResults.innerHTML = `<div class="empty">No headlines match the current filter.</div>`;
    return;
  }
  headlineResults.innerHTML = visible
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
            <span class="pill ${pillClass(item.label)}">${escapeHtml(item.label)}</span>
          </div>
          <div class="score-track">
            <span class="score-fill ${scoreTone(item.score)}" style="width:${scoreWidth(item.score)}%"></span>
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

function renderMeta(meta) {
  const chips = [];
  if (meta.mode) {
    chips.push(meta.mode === "live" ? "Live run" : "Manual run");
  }
  if (meta.provider) {
    chips.push(`Provider ${meta.provider}`);
  }
  if (meta.ticker) {
    chips.push(`Ticker ${meta.ticker}`);
  }
  if (meta.query) {
    chips.push(`Query ${meta.query}`);
  }
  if (meta.headline_count_before_filter && meta.headline_count_after_filter !== undefined) {
    chips.push(`Used ${meta.headline_count_after_filter} of ${meta.headline_count_before_filter}`);
  }
  metaBar.innerHTML = chips.map((chip) => `<span>${escapeHtml(chip)}</span>`).join("");
}

function renderDistribution(result) {
  const buckets = [
    { label: "Bullish", value: result.bullish_count, tone: "positive" },
    { label: "Bearish", value: result.bearish_count, tone: "negative" },
    { label: "Neutral", value: result.neutral_count, tone: "neutral" },
  ];
  const maxValue = Math.max(1, ...buckets.map((bucket) => bucket.value));
  distributionBars.innerHTML = buckets
    .map(
      (bucket) => `
        <div class="dist-row">
          <div class="dist-label">${escapeHtml(bucket.label)}</div>
          <div class="dist-track">
            <span class="dist-fill ${bucket.tone}" style="width:${(bucket.value / maxValue) * 100}%"></span>
          </div>
          <div class="dist-value">${bucket.value}</div>
        </div>
      `
    )
    .join("");
}

function renderSignals(result) {
  const strongest = [
    result.strongest_bullish
      ? signalCard("Strongest Bullish", result.strongest_bullish.headline, signed(result.strongest_bullish.score), "positive")
      : "",
    result.strongest_bearish
      ? signalCard("Strongest Bearish", result.strongest_bearish.headline, signed(result.strongest_bearish.score), "negative")
      : "",
  ].filter(Boolean);
  signalCards.innerHTML = strongest.join("");
}

function renderError(message) {
  currentResult = null;
  summaryCards.innerHTML = "";
  distributionBars.innerHTML = "";
  signalCards.innerHTML = "";
  metaBar.innerHTML = "";
  headlineResults.innerHTML = `<div class="empty">${escapeHtml(message)}</div>`;
  setStatus("Something needs attention.");
}

function setStatus(message) {
  statusLine.textContent = message;
}

function card(label, value) {
  return `<div class="summary-card"><h3>${escapeHtml(label)}</h3><strong>${escapeHtml(value)}</strong></div>`;
}

function signalCard(label, headline, value, tone) {
  return `
    <div class="signal-card ${tone}">
      <div class="signal-label">${escapeHtml(label)}</div>
      <div class="signal-value">${escapeHtml(value)}</div>
      <p>${escapeHtml(headline)}</p>
    </div>
  `;
}

function signed(value) {
  return `${value >= 0 ? "+" : ""}${Number(value).toFixed(2)}`;
}

function matchesCurrentFilter(item) {
  if (currentFilter === "all") {
    return true;
  }
  if (currentFilter === "bullish") {
    return item.score > 0.35;
  }
  if (currentFilter === "bearish") {
    return item.score < -0.35;
  }
  return item.label === "neutral";
}

function pillClass(label) {
  return label.replace(/\s+/g, "-");
}

function scoreTone(score) {
  if (score > 0.35) {
    return "positive";
  }
  if (score < -0.35) {
    return "negative";
  }
  return "neutral";
}

function scoreWidth(score) {
  return Math.max(8, Math.min(100, (Math.abs(score) / 5) * 100));
}

const manualPresets = {
  ai: `NVDA | Reuters | Nvidia surges after strong AI demand
AMD | Bloomberg | AMD wins new hyperscaler chip deal
MSFT | CNBC | Microsoft expands cloud margins on enterprise AI momentum
GOOGL | The Information | Google faces antitrust pressure despite ad growth`,
  volatility: `TSLA | Bloomberg | Tesla drops as deliveries miss expectations
PLTR | Reuters | Palantir rallies after raising full-year guidance
AAPL | CNBC | Apple expands buyback program after strong iPhone sales
SMCI | Barron's | Super Micro swings as margin concerns hit server demand`,
};

const livePresets = {
  nvda: { provider: "alpha_vantage", ticker: "NVDA", query: "", limit: 6 },
  macro: { provider: "newsapi", ticker: "", query: "stocks inflation rates earnings", limit: 6 },
};

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
