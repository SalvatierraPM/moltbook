const DATA_BASE = "../data/derived/";

const files = {
  submoltStats: "submolt_stats.csv",
  diffusionRuns: "diffusion_runs.csv",
  diffusionSubmolts: "diffusion_submolts.csv",
  activityDaily: "activity_daily.csv",
  memeCandidates: "meme_candidates.csv",
  memeClass: "meme_classification.csv",
  memeBursts: "meme_bursts.csv",
  language: "public_language_distribution.csv",
  reply: "reply_graph_centrality.csv",
  mention: "mention_graph_centrality.csv",
  replyCommunities: "reply_graph_communities.csv",
  mentionCommunities: "mention_graph_communities.csv",
  transmission: "public_transmission_samples.csv",
  authors: "author_stats.csv",
  coverage: "coverage_quality.json",
  ontologySummary: "ontology_summary.csv",
  ontologyConcepts: "ontology_concepts_top.csv",
  ontologyCooccurrence: "ontology_cooccurrence_top.csv",
  ontologyEmbedding2d: "ontology_submolt_embedding_2d.csv",
  interferenceSummary: "interference_summary.csv",
  incidenceSummary: "human_incidence_summary.csv",
  interferenceTop: "interference_top.csv",
  incidenceTop: "human_incidence_top.csv",
  embeddingsSummary: "public_embeddings_summary.json",
  embeddingsPostCommentSummary: "embeddings_post_comment/public_embeddings_post_comment_summary.json",
};

const state = {};

function loadCSV(path) {
  if (window.Papa && window.Papa.parse) {
    return new Promise((resolve, reject) => {
      Papa.parse(path, {
        download: true,
        header: true,
        dynamicTyping: true,
        skipEmptyLines: true,
        complete: (res) => resolve(res.data),
        error: (err) => reject(err),
      });
    });
  }
  return fetch(path)
    .then((res) => {
      if (!res.ok) throw new Error(`No se pudo cargar ${path}`);
      return res.text();
    })
    .then(parseCSVFallback);
}

function parseCSVFallback(text) {
  const rows = [];
  let row = [];
  let cur = "";
  let inQuotes = false;
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    if (ch === "\"") {
      if (inQuotes && text[i + 1] === "\"") {
        cur += "\"";
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if ((ch === "," || ch === "\n" || ch === "\r") && !inQuotes) {
      if (ch === ",") {
        row.push(cur);
        cur = "";
        continue;
      }
      row.push(cur);
      cur = "";
      if (row.length > 1 || row[0] !== "") {
        rows.push(row);
      }
      row = [];
      if (ch === "\r" && text[i + 1] === "\n") {
        i += 1;
      }
      continue;
    }
    cur += ch;
  }
  if (cur || row.length) {
    row.push(cur);
    rows.push(row);
  }
  const headers = rows.shift() || [];
  return rows
    .filter((r) => r.length && r.some((cell) => String(cell).trim() !== ""))
    .map((cols) => {
      const obj = {};
      headers.forEach((h, idx) => {
        obj[h] = coerceValue(cols[idx]);
      });
      return obj;
    });
}

function coerceValue(value) {
  if (value === undefined || value === null) return null;
  const raw = String(value).trim();
  if (!raw) return null;
  if (/^-?\d+(\.\d+)?$/.test(raw)) return Number(raw);
  return raw;
}

async function loadJSON(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`No se pudo cargar ${path}`);
  return res.json();
}

function fmtNumber(n) {
  if (n === null || n === undefined || Number.isNaN(n)) return "–";
  return n.toLocaleString("es-ES");
}

function fmtFloat(n, digits = 2) {
  if (n === null || n === undefined || Number.isNaN(n)) return "–";
  return Number(n).toLocaleString("es-ES", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function fmtPercent(n) {
  if (n === null || n === undefined || Number.isNaN(n)) return "–";
  return `${(Number(n) * 100).toFixed(1)}%`;
}

function truncate(text, max = 120) {
  if (!text) return "";
  const clean = String(text).replace(/\s+/g, " ").trim();
  if (clean.length <= max) return clean;
  return `${clean.slice(0, max - 1)}…`;
}

function parseDate(raw) {
  if (!raw) return null;
  const iso = String(raw).replace(" ", "T").replace("+00:00", "Z");
  const dt = new Date(iso);
  return Number.isNaN(dt.getTime()) ? null : dt;
}

function fmtDate(dt) {
  if (!dt) return "–";
  return dt.toISOString().slice(0, 16).replace("T", " ") + " UTC";
}

function mergeSubmoltStats(stats, diffusion) {
  const map = new Map(diffusion.map((r) => [r.submolt, r]));
  return stats.map((r) => {
    const extra = map.get(r.submolt) || {};
    return {
      ...r,
      runs_seen: extra.runs_seen || 0,
      posts_seen_total: extra.posts_seen_total || 0,
      mean_score: extra.mean_score || 0,
      mean_comments: extra.mean_comments || 0,
    };
  });
}

function humanizeFeature(feature) {
  const map = {
    act_request: "peticion",
    act_offer: "oferta",
    act_promise: "promesa",
    act_declaration: "declaracion",
    act_judgment: "juicio",
    act_assertion: "afirmacion",
    act_acceptance: "aceptacion",
    act_rejection: "rechazo",
    act_clarification: "aclaracion",
    act_question_mark: "pregunta",
    mood_ambition: "ambicion",
    mood_resignation: "resignacion",
    mood_resentment: "resentimiento",
    mood_trust: "confianza",
    mood_curiosity: "curiosidad",
    mood_gratitude: "gratitud",
    mood_wonder: "asombro",
    mood_joy: "alegria",
    mood_sadness: "tristeza",
    mood_fear: "miedo",
    mood_anger: "enojo",
    mood_disgust: "asco",
    mood_surprise: "sorpresa",
    epistemic_evidence: "evidencia",
    epistemic_hedge: "atenuacion",
    epistemic_certainty: "certeza",
    epistemic_uncertainty: "incertidumbre",
  };
  if (map[feature]) return map[feature];
  return String(feature || "")
    .replace(/^(act_|mood_|epistemic_)/, "")
    .replace(/_/g, " ");
}

function mountSummary() {
  const totalPosts = state.submolt.reduce((acc, r) => acc + (r.posts || 0), 0);
  const totalComments = state.submolt.reduce((acc, r) => acc + (r.comments || 0), 0);
  const totalSubmolts = state.submolt.length;
  const totalRuns = new Set(state.diffusion.map((r) => r.run_id)).size;
  const totalAuthors = state.authors.length;

  document.querySelector("#total-posts").textContent = fmtNumber(totalPosts);
  document.querySelector("#total-comments").textContent = fmtNumber(totalComments);
  document.querySelector("#total-submolts").textContent = fmtNumber(totalSubmolts);
  document.querySelector("#total-authors").textContent = fmtNumber(totalAuthors);
  document.querySelector("#total-runs").textContent = fmtNumber(totalRuns);

  const coverage = state.coverage || {};
  const createdMins = [coverage.posts_created_min, coverage.comments_created_min]
    .map(parseDate)
    .filter(Boolean);
  const createdMaxs = [coverage.posts_created_max, coverage.comments_created_max]
    .map(parseDate)
    .filter(Boolean);
  const createdMin = createdMins.length ? new Date(Math.min(...createdMins)) : null;
  const createdMax = createdMaxs.length ? new Date(Math.max(...createdMaxs)) : null;
  document.querySelector("#coverage-range").textContent = `${fmtDate(createdMin)} — ${fmtDate(createdMax)}`;
}

function mountCoverageQuality() {
  const coverage = state.coverage || {};
  document.querySelector("#ratio-posts-comments").textContent = fmtFloat(coverage.post_comment_ratio, 2);
  document.querySelector("#dup-posts").textContent = fmtNumber(coverage.posts_duplicates);
  document.querySelector("#dup-comments").textContent = fmtNumber(coverage.comments_duplicates);
  document.querySelector("#range-posts").textContent =
    `${fmtDate(parseDate(coverage.posts_created_min))} — ${fmtDate(parseDate(coverage.posts_created_max))}`;
  document.querySelector("#range-comments").textContent =
    `${fmtDate(parseDate(coverage.comments_created_min))} — ${fmtDate(parseDate(coverage.comments_created_max))}`;
}

function mountEmbeddingsSummary() {
  const emb = state.embeddingsSummary || {};
  const embDocs = document.getElementById("emb-docs");
  if (embDocs) embDocs.textContent = fmtNumber(emb.total_docs);
  const embMatches = document.getElementById("emb-matches");
  if (embMatches) embMatches.textContent = fmtNumber(emb.total_matches);
  const embMean = document.getElementById("emb-mean");
  if (embMean) embMean.textContent = fmtFloat(emb.mean_score, 3);
  const embCross = document.getElementById("emb-cross");
  if (embCross) embCross.textContent = fmtPercent(emb.cross_submolt_rate);
  const embLangs = document.getElementById("emb-langs");
  if (embLangs) embLangs.textContent = fmtNumber(emb.langs_indexed);

  const embPc = state.embeddingsPostCommentSummary || {};
  const embPcPosts = document.getElementById("embpc-posts");
  if (embPcPosts) embPcPosts.textContent = fmtNumber(embPc.total_posts);
  const embPcComments = document.getElementById("embpc-comments");
  if (embPcComments) embPcComments.textContent = fmtNumber(embPc.total_comments);
  const embPcMatches = document.getElementById("embpc-matches");
  if (embPcMatches) embPcMatches.textContent = fmtNumber(embPc.total_matches);
  const embPcMean = document.getElementById("embpc-mean");
  if (embPcMean) embPcMean.textContent = fmtFloat(embPc.mean_score, 3);
  const embPcCross = document.getElementById("embpc-cross");
  if (embPcCross) embPcCross.textContent = fmtPercent(embPc.cross_submolt_rate);
  const embPcLangs = document.getElementById("embpc-langs");
  if (embPcLangs) embPcLangs.textContent = fmtNumber(embPc.langs_indexed);
}

let languageChart;
function mountLanguageChart() {
  const posts = state.language.filter((r) => r.scope === "posts");
  const comments = state.language.filter((r) => r.scope === "comments");

  const combined = {};
  posts.forEach((r) => {
    combined[r.lang] = (combined[r.lang] || 0) + (r.share || 0);
  });
  comments.forEach((r) => {
    combined[r.lang] = (combined[r.lang] || 0) + (r.share || 0);
  });

  const langs = Object.entries(combined)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .map(([lang]) => lang);

  const postMap = Object.fromEntries(posts.map((r) => [r.lang, r.share || 0]));
  const commentMap = Object.fromEntries(comments.map((r) => [r.lang, r.share || 0]));

  const ctx = document.getElementById("language-chart");
  languageChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: langs,
      datasets: [
        {
          label: "Posts",
          data: langs.map((l) => postMap[l] || 0),
          backgroundColor: "rgba(242, 95, 44, 0.65)",
          borderRadius: 8,
        },
        {
          label: "Comentarios",
          data: langs.map((l) => commentMap[l] || 0),
          backgroundColor: "rgba(31, 138, 112, 0.65)",
          borderRadius: 8,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { position: "bottom" } },
      scales: {
        x: { ticks: { color: "#4f4b45" }, grid: { display: false } },
        y: {
          ticks: {
            color: "#4f4b45",
            callback: (value) => `${Math.round(value * 100)}%`,
          },
          grid: { color: "rgba(0,0,0,0.06)" },
        },
      },
    },
  });
}

let submoltChart;
function mountSubmoltChart(metric = "posts") {
  const sorted = [...state.submolt].sort((a, b) => (b[metric] || 0) - (a[metric] || 0));
  const top = sorted.slice(0, 15);

  const ctx = document.getElementById("submolt-chart");
  const labels = top.map((r) => r.submolt);
  const values = top.map((r) => r[metric] || 0);

  if (submoltChart) {
    submoltChart.data.labels = labels;
    submoltChart.data.datasets[0].data = values;
    submoltChart.update();
    return;
  }

  submoltChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: metric,
          data: values,
          backgroundColor: "rgba(242, 95, 44, 0.65)",
          borderRadius: 8,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: {
          ticks: { color: "#4f4b45", maxRotation: 60, minRotation: 40 },
          grid: { display: false },
        },
        y: { ticks: { color: "#4f4b45" }, grid: { color: "rgba(0,0,0,0.06)" } },
      },
    },
  });
}

function mountSubmoltTable() {
  const tableBody = document.querySelector("#submolt-table tbody");
  const rows = [...state.submolt]
    .sort((a, b) => (b.posts || 0) + (b.comments || 0) - ((a.posts || 0) + (a.comments || 0)))
    .slice(0, 25);
  tableBody.innerHTML = rows
    .map(
      (r) => `<tr>
        <td>${r.submolt}</td>
        <td>${fmtNumber(r.posts)}</td>
        <td>${fmtNumber(r.comments)}</td>
        <td>${fmtFloat(r.mean_upvotes)}</td>
        <td>${fmtNumber(r.runs_seen)}</td>
      </tr>`
    )
    .join("");
}

let diffusionChart;
function buildDiffusionSeries(submolt, mode) {
  if (mode === "activity") {
    const data = state.activityDaily.filter((r) => r.submolt === submolt);
    data.sort((a, b) => String(a.date).localeCompare(String(b.date)));
    const labels = data.map((r) => r.date);
    return {
      labels,
      datasets: [
        {
          label: "Posts",
          data: data.map((r) => r.posts || 0),
          borderColor: "#f25f2c",
          backgroundColor: "rgba(242, 95, 44, 0.2)",
          tension: 0.25,
        },
        {
          label: "Comentarios",
          data: data.map((r) => r.comments || 0),
          borderColor: "#1f8a70",
          backgroundColor: "rgba(31, 138, 112, 0.2)",
          tension: 0.25,
          yAxisID: "y2",
        },
      ],
      meta: data,
    };
  }

  const data = state.diffusion.filter((r) => r.submolt === submolt);
  data.sort((a, b) => parseDate(a.run_time) - parseDate(b.run_time));
  const labels = data.map((r) => {
    const dt = parseDate(r.run_time);
    return fmtDate(dt).replace(" UTC", "");
  });
  return {
    labels,
    datasets: [
      {
        label: "Score Medio",
        data: data.map((r) => r.mean_score || 0),
        borderColor: "#f25f2c",
        backgroundColor: "rgba(242, 95, 44, 0.2)",
        tension: 0.25,
      },
      {
        label: "Comentarios Medios",
        data: data.map((r) => r.mean_comments || 0),
        borderColor: "#1f8a70",
        backgroundColor: "rgba(31, 138, 112, 0.2)",
        tension: 0.25,
        yAxisID: "y2",
      },
    ],
    meta: data,
  };
}

function mountDiffusionChart(submolt, mode = "run") {
  const { labels, datasets, meta } = buildDiffusionSeries(submolt, mode);
  const ctx = document.getElementById("diffusion-chart");

  if (diffusionChart) {
    diffusionChart.data.labels = labels;
    diffusionChart.data.datasets = datasets;
    diffusionChart.__meta = { mode, rows: meta };
    diffusionChart.update();
    return;
  }

  diffusionChart = new Chart(ctx, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      plugins: {
        tooltip: {
          callbacks: {
            afterBody: (items) => {
              if (!items.length || !diffusionChart.__meta) return "";
              const meta = diffusionChart.__meta;
              const row = meta.rows[items[0].dataIndex] || {};
              if (meta.mode === "activity") {
                return [`Posts: ${fmtNumber(row.posts || 0)}`, `Comentarios: ${fmtNumber(row.comments || 0)}`];
              }
              return [`Posts vistos: ${fmtNumber(row.posts_seen || 0)}`, `Run: ${row.run_id || ""}`];
            },
          },
        },
      },
      scales: {
        x: { ticks: { color: "#4f4b45" }, grid: { display: false } },
        y: { ticks: { color: "#4f4b45" }, grid: { color: "rgba(0,0,0,0.06)" } },
        y2: {
          position: "right",
          ticks: { color: "#4f4b45" },
          grid: { drawOnChartArea: false },
        },
      },
    },
  });
  diffusionChart.__meta = { mode, rows: meta };
}

function mountDiffusionSelect() {
  const select = document.querySelector("#diffusion-select");
  const modeSelect = document.querySelector("#diffusion-mode");
  const submolts = [...new Set(state.diffusion.map((r) => r.submolt))].sort();
  select.innerHTML = submolts.map((s) => `<option value="${s}">${s}</option>`).join("");
  const defaultSub = submolts.includes("general") ? "general" : submolts[0];
  select.value = defaultSub;
  const defaultMode = modeSelect ? modeSelect.value : "run";
  mountDiffusionChart(defaultSub, defaultMode);

  select.addEventListener("change", (e) => {
    const mode = modeSelect ? modeSelect.value : "run";
    mountDiffusionChart(e.target.value, mode);
  });
  if (modeSelect) {
    modeSelect.addEventListener("change", (e) => {
      mountDiffusionChart(select.value, e.target.value);
    });
  }
}

let memeCandidatesChart;
let memeScatterChart;

function mountMemeCharts() {
  const candidates = [...state.memeCandidates]
    .sort((a, b) => (b.count || 0) - (a.count || 0))
    .slice(0, 12);

  const candCtx = document.getElementById("meme-candidates-chart");
  memeCandidatesChart = new Chart(candCtx, {
    type: "bar",
    data: {
      labels: candidates.map((r) => r.meme),
      datasets: [
        {
          label: "count",
          data: candidates.map((r) => r.count || 0),
          backgroundColor: "rgba(31, 138, 112, 0.6)",
          borderRadius: 8,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: {
          ticks: { color: "#4f4b45", maxRotation: 60, minRotation: 40 },
          grid: { display: false },
        },
        y: { ticks: { color: "#4f4b45" }, grid: { color: "rgba(0,0,0,0.06)" } },
      },
    },
  });

  const toBubble = (r) => {
    const burst = r.burst_score || 0;
    const radius = Math.max(3, Math.min(14, Math.sqrt(burst) / 2));
    return {
      x: r.lifetime_hours || 0,
      y: r.submolts_touched || 0,
      r: radius,
    };
  };

  const local = state.memeClass.filter((r) => r.class === "local").map(toBubble);
  const cross = state.memeClass.filter((r) => r.class === "cross_submolt").map(toBubble);
  const other = state.memeClass
    .filter((r) => r.class !== "local" && r.class !== "cross_submolt")
    .map(toBubble);

  const scatterCtx = document.getElementById("meme-scatter-chart");
  memeScatterChart = new Chart(scatterCtx, {
    type: "bubble",
    data: {
      datasets: [
        {
          label: "Local",
          data: local,
          backgroundColor: "rgba(242, 95, 44, 0.35)",
        },
        {
          label: "Cross-submolt",
          data: cross,
          backgroundColor: "rgba(15, 106, 180, 0.35)",
        },
        {
          label: "Otros",
          data: other,
          backgroundColor: "rgba(31, 138, 112, 0.35)",
        },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { position: "bottom" } },
      scales: {
        x: {
          title: { display: true, text: "Vida (hrs)" },
          ticks: { color: "#4f4b45" },
          grid: { color: "rgba(0,0,0,0.06)" },
        },
        y: {
          title: { display: true, text: "Submolts tocados" },
          ticks: { color: "#4f4b45" },
          grid: { color: "rgba(0,0,0,0.06)" },
        },
      },
    },
  });
}

function mountMemeSurvivalTable() {
  const tableBody = document.querySelector("#meme-survival-table tbody");
  const rows = [...state.memeClass]
    .sort((a, b) => (b.lifetime_hours || 0) - (a.lifetime_hours || 0))
    .slice(0, 20);
  tableBody.innerHTML = rows
    .map(
      (r) => `<tr>
        <td>${r.meme}</td>
        <td>${fmtFloat(r.lifetime_hours, 1)}</td>
        <td>${fmtFloat(r.burst_score, 1)}</td>
        <td>${r.class || "–"}</td>
      </tr>`
    )
    .join("");
}

function mountMemeBurstTable() {
  const tableBody = document.querySelector("#meme-burst-table tbody");
  const rows = state.memeBursts
    .map((r) => {
      const start = parseDate(r.start_hour);
      const end = parseDate(r.end_hour);
      const duration = start && end ? (end - start) / 3600000 : 0;
      return {
        ...r,
        duration,
        start,
        end,
      };
    })
    .sort((a, b) => (b.burst_level || 0) - (a.burst_level || 0) || b.duration - a.duration)
    .slice(0, 20);

  tableBody.innerHTML = rows
    .map(
      (r) => `<tr>
        <td>${r.meme}</td>
        <td>${fmtNumber(r.burst_level)}</td>
        <td>${fmtDate(r.start)}</td>
        <td>${fmtDate(r.end)}</td>
        <td>${fmtFloat(r.duration, 1)}</td>
      </tr>`
    )
    .join("");
}

let ontologyActsChart;
let ontologyMoodsChart;
let ontologyEpistemicChart;

function buildOntologySeries(prefix, limit = 8) {
  return state.ontologySummary
    .filter((r) => r.scope === "all" && String(r.feature || "").startsWith(prefix))
    .sort((a, b) => (b.count || 0) - (a.count || 0))
    .slice(0, limit);
}

function mountOntologyCharts() {
  const acts = buildOntologySeries("act_", 8);
  const moods = buildOntologySeries("mood_", 8);
  const epistemic = buildOntologySeries("epistemic_", 6);

  ontologyActsChart = new Chart(document.getElementById("ontology-acts-chart"), {
    type: "bar",
    data: {
      labels: acts.map((r) => humanizeFeature(r.feature)),
      datasets: [
        {
          label: "conteo",
          data: acts.map((r) => r.count || 0),
          backgroundColor: "rgba(242, 95, 44, 0.6)",
          borderRadius: 8,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#4f4b45" }, grid: { display: false } },
        y: { ticks: { color: "#4f4b45" }, grid: { color: "rgba(0,0,0,0.06)" } },
      },
    },
  });

  ontologyMoodsChart = new Chart(document.getElementById("ontology-moods-chart"), {
    type: "bar",
    data: {
      labels: moods.map((r) => humanizeFeature(r.feature)),
      datasets: [
        {
          label: "conteo",
          data: moods.map((r) => r.count || 0),
          backgroundColor: "rgba(31, 138, 112, 0.6)",
          borderRadius: 8,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#4f4b45" }, grid: { display: false } },
        y: { ticks: { color: "#4f4b45" }, grid: { color: "rgba(0,0,0,0.06)" } },
      },
    },
  });

  ontologyEpistemicChart = new Chart(document.getElementById("ontology-epistemic-chart"), {
    type: "bar",
    data: {
      labels: epistemic.map((r) => humanizeFeature(r.feature)),
      datasets: [
        {
          label: "conteo",
          data: epistemic.map((r) => r.count || 0),
          backgroundColor: "rgba(15, 106, 180, 0.6)",
          borderRadius: 8,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#4f4b45" }, grid: { display: false } },
        y: { ticks: { color: "#4f4b45" }, grid: { color: "rgba(0,0,0,0.06)" } },
      },
    },
  });
}

function mountOntologyTables() {
  const actsBody = document.querySelector("#ontology-acts-table tbody");
  const conceptsBody = document.querySelector("#ontology-concepts-table tbody");
  const pairsBody = document.querySelector("#ontology-cooccurrence-table tbody");

  const acts = buildOntologySeries("act_", 12);
  actsBody.innerHTML = acts
    .map(
      (r) => `<tr>
        <td>${humanizeFeature(r.feature)}</td>
        <td>${fmtNumber(r.count)}</td>
        <td>${fmtFloat(r.rate_per_doc, 3)}</td>
      </tr>`
    )
    .join("");

  const concepts = [...state.ontologyConcepts].slice(0, 15);
  conceptsBody.innerHTML = concepts
    .map(
      (r) => `<tr>
        <td>${r.concept}</td>
        <td>${fmtNumber(r.doc_count ?? r.count)}</td>
        <td>${fmtPercent(r.share)}</td>
      </tr>`
    )
    .join("");

  const pairs = [...state.ontologyCooccurrence].slice(0, 15);
  pairsBody.innerHTML = pairs
    .map(
      (r) => `<tr>
        <td>${r.concept_a}</td>
        <td>${r.concept_b}</td>
        <td>${fmtNumber(r.count)}</td>
      </tr>`
    )
    .join("");
}

let ontologyMapChart;
function mountOntologyMap() {
  const rows = [...(state.ontologyEmbedding2d || [])]
    .sort((a, b) => (b.doc_count || 0) - (a.doc_count || 0))
    .slice(0, 250);

  const points = rows.map((r) => {
    const size = Math.max(3, Math.min(16, Math.sqrt(r.doc_count || 1) / 2));
    return {
      x: r.x || 0,
      y: r.y || 0,
      r: size,
      label: r.submolt,
      doc_count: r.doc_count || 0,
    };
  });

  const ctx = document.getElementById("ontology-map-chart");
  ontologyMapChart = new Chart(ctx, {
    type: "bubble",
    data: {
      datasets: [
        {
          label: "Submolts",
          data: points,
          backgroundColor: "rgba(15, 106, 180, 0.35)",
          borderColor: "rgba(15, 106, 180, 0.6)",
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (context) => {
              const raw = context.raw || {};
              return `${raw.label} (n=${fmtNumber(raw.doc_count)})`;
            },
          },
        },
      },
      scales: {
        x: {
          ticks: { color: "#4f4b45" },
          grid: { color: "rgba(0,0,0,0.06)" },
          title: { display: true, text: "Componente 1 (PCA)" },
        },
        y: {
          ticks: { color: "#4f4b45" },
          grid: { color: "rgba(0,0,0,0.06)" },
          title: { display: true, text: "Componente 2 (PCA)" },
        },
      },
    },
  });
}

let interferenceChart;
let incidenceChart;

function mountInterferenceCharts() {
  const scopes = ["all", "posts", "comments"];
  const interference = scopes.map(
    (scope) => state.interferenceSummary.find((r) => r.scope === scope) || {}
  );
  const incidence = scopes.map(
    (scope) => state.incidenceSummary.find((r) => r.scope === scope) || {}
  );

  interferenceChart = new Chart(document.getElementById("interference-chart"), {
    type: "bar",
    data: {
      labels: ["All", "Posts", "Comentarios"],
      datasets: [
        {
          label: "score promedio",
          data: interference.map((r) => r.avg_score || 0),
          backgroundColor: "rgba(242, 95, 44, 0.6)",
          borderRadius: 8,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#4f4b45" }, grid: { display: false } },
        y: { ticks: { color: "#4f4b45" }, grid: { color: "rgba(0,0,0,0.06)" } },
      },
    },
  });

  incidenceChart = new Chart(document.getElementById("incidence-chart"), {
    type: "bar",
    data: {
      labels: ["All", "Posts", "Comentarios"],
      datasets: [
        {
          label: "score promedio",
          data: incidence.map((r) => r.avg_score || 0),
          backgroundColor: "rgba(31, 138, 112, 0.6)",
          borderRadius: 8,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#4f4b45" }, grid: { display: false } },
        y: { ticks: { color: "#4f4b45" }, grid: { color: "rgba(0,0,0,0.06)" } },
      },
    },
  });
}

function mountInterferenceTables() {
  const interferenceBody = document.querySelector("#interference-table tbody");
  const incidenceBody = document.querySelector("#incidence-table tbody");

  const interRows = [...state.interferenceTop].slice(0, 30);
  interferenceBody.innerHTML = interRows
    .map(
      (r) => `<tr>
        <td>${String(r.doc_id || "").slice(0, 8)}</td>
        <td>${r.doc_type}</td>
        <td>${r.submolt}</td>
        <td>${fmtFloat(r.score, 1)}</td>
        <td>${fmtNumber((r.injection_hits || 0) + (r.disclaimer_hits || 0))}</td>
        <td>${truncate(r.text_excerpt, 120)}</td>
      </tr>`
    )
    .join("");

  const incRows = [...state.incidenceTop].slice(0, 30);
  incidenceBody.innerHTML = incRows
    .map(
      (r) => `<tr>
        <td>${String(r.doc_id || "").slice(0, 8)}</td>
        <td>${r.doc_type}</td>
        <td>${r.submolt}</td>
        <td>${fmtFloat(r.human_incidence_score, 1)}</td>
        <td>${fmtNumber((r.human_refs || 0) + (r.prompt_refs || 0))}</td>
        <td>${truncate(r.text_excerpt, 120)}</td>
      </tr>`
    )
    .join("");
}

function mountTransmissionTable() {
  const select = document.getElementById("transmission-submolt");
  const search = document.getElementById("transmission-search");
  const body = document.querySelector("#transmission-table tbody");

  const submolts = ["all", ...new Set(state.transmission.map((r) => r.submolt || "unknown"))].sort();
  select.innerHTML = submolts.map((s) => `<option value="${s}">${s}</option>`).join("");

  const render = () => {
    const sub = select.value;
    const term = search.value.toLowerCase();
    const rows = state.transmission
      .filter((r) => (sub === "all" ? true : (r.submolt || "unknown") === sub))
      .filter((r) => String(r.text || "").toLowerCase().includes(term))
      .slice(0, 80);

    body.innerHTML = rows
      .map(
        (r) => `<tr>
          <td>${r.source}</td>
          <td>${r.submolt || "unknown"}</td>
          <td>${String(r.created_at || "").slice(0, 16).replace("T", " ")}</td>
          <td>${r.text}</td>
        </tr>`
      )
      .join("");
  };

  select.addEventListener("change", render);
  search.addEventListener("input", render);
  render();
}

function mountNetworkTables() {
  const replyBody = document.querySelector("#reply-table tbody");
  const mentionBody = document.querySelector("#mention-table tbody");

  const replyRows = [...state.reply].slice(0, 50);
  const mentionRows = [...state.mention].slice(0, 50);

  const renderRows = (rows) =>
    rows
      .map(
        (r) => `<tr>
          <td>${r.node}</td>
          <td>${fmtFloat(r.pagerank, 6)}</td>
          <td>${fmtFloat(r.betweenness, 6)}</td>
          <td>${fmtNumber(r.in_degree)}</td>
          <td>${fmtNumber(r.out_degree)}</td>
        </tr>`
      )
      .join("");

  replyBody.innerHTML = renderRows(replyRows);
  mentionBody.innerHTML = renderRows(mentionRows);

  const replySearch = document.getElementById("reply-search");
  replySearch.addEventListener("input", () => {
    const term = replySearch.value.toLowerCase();
    const filtered = state.reply
      .filter((r) => String(r.node).toLowerCase().includes(term))
      .slice(0, 50);
    replyBody.innerHTML = renderRows(filtered);
  });

  const mentionSearch = document.getElementById("mention-search");
  mentionSearch.addEventListener("input", () => {
    const term = mentionSearch.value.toLowerCase();
    const filtered = state.mention
      .filter((r) => String(r.node).toLowerCase().includes(term))
      .slice(0, 50);
    mentionBody.innerHTML = renderRows(filtered);
  });
}

function mountCommunityTables() {
  const replyBody = document.querySelector("#reply-community-table tbody");
  const mentionBody = document.querySelector("#mention-community-table tbody");

  const summarize = (rows) => {
    const counts = new Map();
    rows.forEach((r) => {
      const key = String(r.community);
      counts.set(key, (counts.get(key) || 0) + 1);
    });
    return [...counts.entries()]
      .map(([community, count]) => ({ community, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 12);
  };

  const replyRows = summarize(state.replyCommunities || []);
  const mentionRows = summarize(state.mentionCommunities || []);

  replyBody.innerHTML = replyRows
    .map((r) => `<tr><td>${r.community}</td><td>${fmtNumber(r.count)}</td></tr>`)
    .join("");
  mentionBody.innerHTML = mentionRows
    .map((r) => `<tr><td>${r.community}</td><td>${fmtNumber(r.count)}</td></tr>`)
    .join("");
}

function mountAuthorTable() {
  const body = document.querySelector("#author-table tbody");
  const search = document.getElementById("author-search");

  const sorted = [...state.authors]
    .map((r) => ({
      ...r,
      total_activity: (r.posts || 0) + (r.comments || 0),
    }))
    .sort((a, b) => b.total_activity - a.total_activity);

  const render = () => {
    const term = search.value.toLowerCase();
    const rows = sorted
      .filter((r) => String(r.author_id).toLowerCase().includes(term))
      .slice(0, 50);

    body.innerHTML = rows
      .map(
        (r) => `<tr>
          <td>${r.author_id}</td>
          <td>${fmtNumber(r.posts)}</td>
          <td>${fmtNumber(r.comments)}</td>
          <td>${fmtNumber(r.post_submolts)}</td>
          <td>${fmtNumber(r.comment_submolts)}</td>
        </tr>`
      )
      .join("");
  };

  search.addEventListener("input", render);
  render();
}

function attachSubmoltToggle() {
  const buttons = document.querySelectorAll(".toggle");
  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      buttons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const metric = btn.dataset.metric;
      mountSubmoltChart(metric);
    });
  });
}

async function init() {
  const [
    submoltStats,
    diffusionRuns,
    diffusionSubmolts,
    activityDaily,
    memeCandidates,
    memeClass,
    memeBursts,
    language,
    reply,
    mention,
    replyCommunities,
    mentionCommunities,
    transmission,
    authors,
    coverage,
    ontologySummary,
    ontologyConcepts,
    ontologyCooccurrence,
    ontologyEmbedding2d,
    interferenceSummary,
    incidenceSummary,
    interferenceTop,
    incidenceTop,
    embeddingsSummary,
    embeddingsPostCommentSummary,
  ] = await Promise.all([
    loadCSV(DATA_BASE + files.submoltStats),
    loadCSV(DATA_BASE + files.diffusionRuns),
    loadCSV(DATA_BASE + files.diffusionSubmolts),
    loadCSV(DATA_BASE + files.activityDaily),
    loadCSV(DATA_BASE + files.memeCandidates),
    loadCSV(DATA_BASE + files.memeClass),
    loadCSV(DATA_BASE + files.memeBursts),
    loadCSV(DATA_BASE + files.language),
    loadCSV(DATA_BASE + files.reply),
    loadCSV(DATA_BASE + files.mention),
    loadCSV(DATA_BASE + files.replyCommunities),
    loadCSV(DATA_BASE + files.mentionCommunities),
    loadCSV(DATA_BASE + files.transmission),
    loadCSV(DATA_BASE + files.authors),
    loadJSON(DATA_BASE + files.coverage),
    loadCSV(DATA_BASE + files.ontologySummary),
    loadCSV(DATA_BASE + files.ontologyConcepts),
    loadCSV(DATA_BASE + files.ontologyCooccurrence),
    loadCSV(DATA_BASE + files.ontologyEmbedding2d),
    loadCSV(DATA_BASE + files.interferenceSummary),
    loadCSV(DATA_BASE + files.incidenceSummary),
    loadCSV(DATA_BASE + files.interferenceTop),
    loadCSV(DATA_BASE + files.incidenceTop),
    loadJSON(DATA_BASE + files.embeddingsSummary),
    loadJSON(DATA_BASE + files.embeddingsPostCommentSummary),
  ]);

  state.submolt = mergeSubmoltStats(submoltStats, diffusionSubmolts);
  state.diffusion = diffusionRuns;
  state.activityDaily = activityDaily;
  state.memeCandidates = memeCandidates;
  state.memeClass = memeClass;
  state.memeBursts = memeBursts;
  state.language = language;
  state.reply = reply;
  state.mention = mention;
  state.replyCommunities = replyCommunities;
  state.mentionCommunities = mentionCommunities;
  state.transmission = transmission;
  state.authors = authors;
  state.coverage = coverage;
  state.ontologySummary = ontologySummary;
  state.ontologyConcepts = ontologyConcepts;
  state.ontologyCooccurrence = ontologyCooccurrence;
  state.ontologyEmbedding2d = ontologyEmbedding2d;
  state.interferenceSummary = interferenceSummary;
  state.incidenceSummary = incidenceSummary;
  state.interferenceTop = interferenceTop;
  state.incidenceTop = incidenceTop;
  state.embeddingsSummary = embeddingsSummary;
  state.embeddingsPostCommentSummary = embeddingsPostCommentSummary;

  mountSummary();
  mountCoverageQuality();
  mountEmbeddingsSummary();
  mountLanguageChart();
  mountSubmoltChart("posts");
  mountSubmoltTable();
  attachSubmoltToggle();
  mountDiffusionSelect();
  mountInterferenceCharts();
  mountInterferenceTables();
  mountMemeCharts();
  mountMemeSurvivalTable();
  mountMemeBurstTable();
  mountOntologyCharts();
  mountOntologyMap();
  mountOntologyTables();
  mountTransmissionTable();
  mountNetworkTables();
  mountCommunityTables();
  mountAuthorTable();
}

init().catch((err) => {
  console.error(err);
  document.body.insertAdjacentHTML(
    "beforeend",
    `<div style=\"padding:24px;color:#b00020\">No se pudieron cargar los datos. Sirve el sitio desde la raiz del repo para que ../data/derived sea accesible.</div>`
  );
});
