const Core = window.AnalyticsCore;
if (!Core) throw new Error("AnalyticsCore no está cargado");

const DATA_BASE = Core.DATA_BASE;

const files = {
  submoltStats: "submolt_stats.csv",
  diffusionRuns: "diffusion_runs.csv",
  diffusionSubmolts: "diffusion_submolts.csv",
  memeCandidates: "meme_candidates.csv",
  memeCandidatesTechnical: "meme_candidates_technical.csv",
  memeCandidatesCultural: "meme_candidates_cultural.csv",
  memeClass: "meme_classification.csv",
  memeBursts: "meme_bursts.csv",
  language: "public_language_distribution.csv",
  reply: "reply_graph_centrality.csv",
  replySummary: "reply_graph_summary.json",
  mention: "mention_graph_centrality.csv",
  mentionSummary: "mention_graph_summary.json",
  replyCommunities: "reply_graph_communities.csv",
  mentionCommunities: "mention_graph_communities.csv",
  transmission: "public_transmission_samples.csv",
  authors: "author_stats.csv",
  coverage: "coverage_quality.json",
  ontologySummary: "ontology_summary.csv",
  ontologyConcepts: "ontology_concepts_top.csv",
  ontologyCooccurrence: "ontology_cooccurrence_top.csv",
  ontologyEmbedding2d: "ontology_submolt_embedding_2d.csv",
  ontologySubmoltFull: "ontology_submolt_full.csv",
  interferenceSummary: "interference_summary.csv",
  embeddingsSummary: "public_embeddings_summary.json",
  embeddingsPostCommentSummary: "embeddings_post_comment/public_embeddings_post_comment_summary.json",
  docLookup: "public_doc_lookup.json",
  sociologyInterpretation: "public_sociology_interpretation.json",
};

const state = {};
state.filters = {
  hideLanguageEn: false,
  hideSubmoltGeneral: false,
};
state.reply = [];
state.replySummary = {};
state.mention = [];
state.mentionSummary = {};
state.replyCommunities = [];
state.mentionCommunities = [];
state.authors = [];
state.authorsLoaded = false;
state.docLookup = {};
state.docLookupLoaded = false;
state.docLookupPromise = null;

const LIMITS = {
  submoltTable: 50,
  memeSurvivalTable: 25,
  memeBurstTable: 20,
  ontologyConceptsTable: 30,
  ontologyCooccurrenceTable: 30,
};

let concentrationTop5Chart;
let concentrationLorenzChart;
let memeLayerChart;
let ontologyCompareChart;
let networkConcentrationChart;

const TRANSMISSION_TEXT_MIN_CHARS = Core.TRANSMISSION_TEXT_MIN_CHARS;
const METRIC_CONTRACT_ROWS = Core.METRIC_CONTRACT_ROWS;
const loadCSV = Core.loadCSV;
const loadJSON = Core.loadJSON;
const parseDate = Core.parseDate;
const conceptLemma = Core.conceptLemma;
const isVariantPair = Core.isVariantPair;
const buildTransmissionPool = Core.buildTransmissionPool;

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

function clamp01(n) {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return 0;
  return Math.max(0, Math.min(1, Number(n)));
}

function calcGini(values) {
  const clean = (values || [])
    .map((v) => Number(v) || 0)
    .filter((v) => Number.isFinite(v) && v >= 0)
    .sort((a, b) => a - b);
  const n = clean.length;
  if (!n) return null;
  const total = clean.reduce((acc, v) => acc + v, 0);
  if (total <= 0) return 0;
  let weighted = 0;
  for (let i = 0; i < n; i += 1) {
    weighted += (i + 1) * clean[i];
  }
  return (2 * weighted) / (n * total) - (n + 1) / n;
}

function buildCumulativeCurve(values, { descending = false } = {}) {
  const clean = (values || [])
    .map((v) => Number(v) || 0)
    .filter((v) => Number.isFinite(v) && v >= 0)
    .sort((a, b) => (descending ? b - a : a - b));
  if (!clean.length) return [{ x: 0, y: 0 }, { x: 1, y: 1 }];
  const total = clean.reduce((acc, v) => acc + v, 0);
  if (total <= 0) return [{ x: 0, y: 0 }, { x: 1, y: 1 }];
  const points = [{ x: 0, y: 0 }];
  let cumulative = 0;
  clean.forEach((v, idx) => {
    cumulative += v;
    points.push({
      x: (idx + 1) / clean.length,
      y: cumulative / total,
    });
  });
  return points;
}

function shareTop(values, count) {
  const clean = (values || [])
    .map((v) => Number(v) || 0)
    .filter((v) => Number.isFinite(v) && v >= 0)
    .sort((a, b) => b - a);
  if (!clean.length) return { share: null, topCount: 0, total: 0 };
  const topCount = Math.max(0, Math.min(clean.length, Math.floor(count)));
  const total = clean.reduce((acc, v) => acc + v, 0);
  if (topCount === 0 || total <= 0) return { share: 0, topCount, total };
  const top = clean.slice(0, topCount).reduce((acc, v) => acc + v, 0);
  return { share: top / total, topCount, total };
}

function truncate(text, max = 120) {
  if (!text) return "";
  const clean = String(text).replace(/\s+/g, " ").trim();
  if (clean.length <= max) return clean;
  return `${clean.slice(0, max - 1)}…`;
}

function escapeHtml(text) {
  return String(text || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;")
    .replaceAll("'", "&#039;");
}

function setText(id, value) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = value;
}

function setChip(id, label, tone = "neutral") {
  const el = document.getElementById(id);
  if (!el) return;
  el.className = `status-chip status-${tone}`;
  el.textContent = label;
}

function renderMeter(value, max, suffix = "") {
  const safeMax = Math.max(Number(max) || 0, 1);
  const raw = Number(value) || 0;
  const ratio = Math.max(0, Math.min(1, raw / safeMax));
  const width = Math.round(ratio * 100);
  const suffixText = suffix ? ` <span class="metric-suffix">${escapeHtml(suffix)}</span>` : "";
  return `<div class="metric-meter"><span class="metric-fill" style="width:${width}%"></span></div><span class="metric-value">${fmtNumber(raw)}${suffixText}</span>`;
}

function ensureTextModal() {
  let overlay = document.getElementById("text-modal-overlay");
  if (overlay) return overlay;
  document.body.insertAdjacentHTML(
    "beforeend",
    `<div class="modal-overlay" id="text-modal-overlay" aria-hidden="true">
      <div class="modal" role="dialog" aria-modal="true" aria-labelledby="text-modal-title">
        <div class="modal-head">
          <div class="modal-head-copy">
            <div class="modal-title" id="text-modal-title">Texto completo</div>
            <div class="modal-meta" id="text-modal-meta"></div>
          </div>
          <button class="toggle modal-close" id="text-modal-close" type="button">Cerrar</button>
        </div>
        <div class="modal-body">
          <pre class="modal-pre" id="text-modal-text"></pre>
        </div>
      </div>
    </div>`
  );
  overlay = document.getElementById("text-modal-overlay");
  const closeBtn = document.getElementById("text-modal-close");
  const close = () => {
    overlay.classList.remove("open");
    overlay.setAttribute("aria-hidden", "true");
    document.body.classList.remove("modal-open");
  };
  closeBtn.addEventListener("click", close);
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) close();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") close();
  });
  overlay.__close = close;
  return overlay;
}

function openTextModal({ title, meta, text }) {
  const overlay = ensureTextModal();
  const titleEl = document.getElementById("text-modal-title");
  const metaEl = document.getElementById("text-modal-meta");
  const textEl = document.getElementById("text-modal-text");
  titleEl.textContent = title || "Texto completo";
  metaEl.textContent = meta || "";
  textEl.textContent = text || "(texto no disponible)";
  overlay.classList.add("open");
  overlay.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
}

function lookupDocText(docId) {
  if (!docId || !state.docLookup) return null;
  const hit = state.docLookup[String(docId)];
  if (hit && typeof hit.text === "string") return hit.text;
  return null;
}

async function ensureDocLookupLoaded() {
  if (state.docLookupLoaded) return state.docLookup;
  if (!state.docLookupPromise) {
    state.docLookupPromise = loadJSON(DATA_BASE + files.docLookup)
      .then((payload) => {
        state.docLookup = (payload && payload.docs) || {};
        return state.docLookup;
      })
      .catch(() => {
        state.docLookup = {};
        return state.docLookup;
      })
      .finally(() => {
        state.docLookupLoaded = true;
        state.docLookupPromise = null;
      });
  }
  return state.docLookupPromise;
}

function attachTextModalDelegation() {
  document.addEventListener("click", async (e) => {
    const target = e.target && e.target.closest ? e.target.closest(".text-link[data-doc-id]") : null;
    if (!target) return;
    e.preventDefault();
    const docId = target.dataset.docId;
    const docType = target.dataset.docType || "";
    const submolt = target.dataset.docSubmolt || "";
    const createdAt = target.dataset.docCreatedAt || "";
    const score = target.dataset.docScore || "";
    let text = lookupDocText(docId) || "";
    if (!text) {
      await ensureDocLookupLoaded();
      text = lookupDocText(docId) || "";
    }
    const meta = [docType && `tipo=${docType}`, submolt && `submolt=${submolt}`, createdAt && `fecha=${createdAt}`, score && `score=${score}`]
      .filter(Boolean)
      .join(" · ");
    openTextModal({ title: `Doc ${String(docId).slice(0, 8)}`, meta, text });
  });
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

function submoltVolumes() {
  return (state.submolt || []).map((r) => (Number(r.posts) || 0) + (Number(r.comments) || 0));
}

function submoltConcentrationStats() {
  const volumes = submoltVolumes();
  const totalSubmolts = volumes.length;
  const top5 = shareTop(volumes, 5);
  const top2Count = Math.max(1, Math.ceil(totalSubmolts * 0.02));
  const top2 = shareTop(volumes, top2Count);
  return {
    volumes,
    totalSubmolts,
    top5Share: top5.share,
    top2Share: top2.share,
    top2Count,
    gini: calcGini(volumes),
  };
}

function memeLayerStats() {
  const technicalRows = state.memeCandidatesTechnical || [];
  const culturalRows = state.memeCandidatesCultural || [];
  const technicalCount = technicalRows.reduce((acc, r) => acc + (Number(r.count) || 0), 0);
  const culturalCount = culturalRows.reduce((acc, r) => acc + (Number(r.count) || 0), 0);
  const total = technicalCount + culturalCount;
  return {
    technicalRows,
    culturalRows,
    technicalCount,
    culturalCount,
    total,
    technicalShare: total > 0 ? technicalCount / total : null,
    culturalShare: total > 0 ? culturalCount / total : null,
  };
}

function humanizeFeature(feature) {
  const map = {
    act_request: "petición",
    act_offer: "oferta",
    act_promise: "promesa",
    act_declaration: "declaración",
    act_judgment: "juicio",
    act_assertion: "afirmación",
    act_acceptance: "aceptación",
    act_rejection: "rechazo",
    act_clarification: "aclaración",
    act_question_mark: "pregunta",
    mood_ambition: "ambición",
    mood_resignation: "resignación",
    mood_resentment: "resentimiento",
    mood_trust: "confianza",
    mood_curiosity: "curiosidad",
    mood_gratitude: "gratitud",
    mood_wonder: "asombro",
    mood_joy: "alegría",
    mood_sadness: "tristeza",
    mood_fear: "miedo",
    mood_anger: "enojo",
    mood_disgust: "asco",
    mood_surprise: "sorpresa",
    epistemic_evidence: "evidencia",
    epistemic_hedge: "atenuación",
    epistemic_certainty: "certeza",
    epistemic_uncertainty: "incertidumbre",
  };
  if (map[feature]) return map[feature];
  return String(feature || "")
    .replace(/^(act_|mood_|epistemic_)/, "")
    .replace(/_/g, " ");
}


function sumLanguageShare(scope) {
  return Core.sumLanguageShare(state.language || [], scope);
}

function sumLanguageCount(scope) {
  return Core.sumLanguageCount(state.language || [], scope);
}

function mountMetricContract() {
  const body = document.querySelector("#analysis-metric-contract-table tbody");
  if (!body) return;
  body.innerHTML = METRIC_CONTRACT_ROWS.map(
    ([module, metric, source, transform, axis]) => `<tr>
      <td>${escapeHtml(module)}</td>
      <td>${escapeHtml(metric)}</td>
      <td>${escapeHtml(source)}</td>
      <td>${escapeHtml(transform)}</td>
      <td>${escapeHtml(axis)}</td>
    </tr>`
  ).join("");
}

function mountActiveFiltersSummary() {
  const body = document.querySelector("#analysis-active-filters-table tbody");
  if (!body) return;
  const pairRows = state.ontologyCooccurrence || [];
  const variants = pairRows.filter((r) => isVariantPair(r.concept_a, r.concept_b)).length;
  const tx = state.transmissionPolicy || buildTransmissionPool(state.transmission || []);
  const visibleTx = Number(state.transmissionVisibleCount || 0);
  const rows = [
    [
      "Ontología",
      "Excluir pares variantes (lemma equivalente)",
      "activo",
      `${fmtNumber(variants)} pares variantes excluidos del ranking`,
    ],
    [
      "Transmisión",
      `Texto >= ${TRANSMISSION_TEXT_MIN_CHARS} chars + prioridad co-mención humano+IA`,
      "activo",
      `Pool=${fmtNumber(tx.pool.length)} de ${fmtNumber(tx.totals.raw)} (${tx.policy}); vista=${fmtNumber(visibleTx)}`,
    ],
    [
      "Idiomas",
      "Ocultar inglés (en)",
      state.filters.hideLanguageEn ? "activo" : "inactivo",
      state.filters.hideLanguageEn ? "El ranking visual excluye 'en'" : "Se muestran todos los idiomas",
    ],
    [
      "Submolts",
      "Ocultar general",
      state.filters.hideSubmoltGeneral ? "activo" : "inactivo",
      state.filters.hideSubmoltGeneral ? "Se excluye 'general' en volumen comparativo" : "Sin exclusiones de submolt",
    ],
  ];
  body.innerHTML = rows
    .map(
      ([module, filter, status, impact]) => `<tr>
        <td>${escapeHtml(module)}</td>
        <td>${escapeHtml(filter)}</td>
        <td>${escapeHtml(status)}</td>
        <td>${escapeHtml(impact)}</td>
      </tr>`
    )
    .join("");
}

function mountTraceability() {
  const body = document.querySelector("#analysis-traceability-table tbody");
  if (!body) return;
  const coverage = state.coverage || {};
  const createdMins = [coverage.posts_created_min, coverage.comments_created_min].map(parseDate).filter(Boolean);
  const createdMaxs = [coverage.posts_created_max, coverage.comments_created_max].map(parseDate).filter(Boolean);
  const createdMin = createdMins.length ? new Date(Math.min(...createdMins)) : null;
  const createdMax = createdMaxs.length ? new Date(Math.max(...createdMaxs)) : null;
  const runDates = (state.diffusion || []).map((r) => parseDate(r.run_time)).filter(Boolean);
  const runMin = runDates.length ? new Date(Math.min(...runDates)) : null;
  const runMax = runDates.length ? new Date(Math.max(...runDates)) : null;
  const totalRuns = new Set((state.diffusion || []).map((r) => r.run_id)).size;
  const totalPosts = (state.submolt || []).reduce((acc, r) => acc + (r.posts || 0), 0);
  const totalComments = (state.submolt || []).reduce((acc, r) => acc + (r.comments || 0), 0);
  const tx = state.transmissionPolicy || buildTransmissionPool(state.transmission || []);
  const rows = [
    [
      "Rango created_at",
      `${fmtDate(createdMin)} — ${fmtDate(createdMax)}`,
    ],
    ["Rango run_time", `${fmtDate(runMin)} — ${fmtDate(runMax)}`],
    ["Runs únicos", fmtNumber(totalRuns)],
    ["Volumen snapshot", `${fmtNumber(totalPosts)} posts / ${fmtNumber(totalComments)} comentarios`],
    [
      "Muestra idioma",
      `${fmtNumber(sumLanguageCount("posts"))} posts + ${fmtNumber(sumLanguageCount("comments"))} comentarios`,
    ],
    ["Muestra transmisión", `${fmtNumber(tx.pool.length)} docs (de ${fmtNumber(tx.totals.raw)} raw)`],
    ["Política transmisión activa", tx.policy],
    ["Versión criterios", "v1.1 (co-ocurrencia sin variantes + transmisión canónica)"],
  ];
  body.innerHTML = rows
    .map(
      ([item, value]) => `<tr>
        <td>${escapeHtml(item)}</td>
        <td>${escapeHtml(value)}</td>
      </tr>`
    )
    .join("");
}

function mountCoherenceCheck() {
  const body = document.querySelector("#analysis-coherence-table tbody");
  if (!body) return;
  const cooccRows = (state.ontologyCooccurrence || [])
    .filter((r) => !isVariantPair(r.concept_a, r.concept_b))
    .slice(0, LIMITS.ontologyCooccurrenceTable);
  const hasVariantInTop = cooccRows.some((r) => isVariantPair(r.concept_a, r.concept_b));

  const rebuiltTx = buildTransmissionPool(state.transmission || []);
  const tx = state.transmissionPolicy || rebuiltTx;
  const txPolicyMatch = tx.pool.length === rebuiltTx.pool.length && tx.policy === rebuiltTx.policy;

  const postShare = sumLanguageShare("posts");
  const commentShare = sumLanguageShare("comments");
  const languageShareOk = Math.abs(postShare - 1) <= 0.03 && Math.abs(commentShare - 1) <= 0.03;

  const coverage = state.coverage || {};
  const postsMin = parseDate(coverage.posts_created_min);
  const postsMax = parseDate(coverage.posts_created_max);
  const commentsMin = parseDate(coverage.comments_created_min);
  const commentsMax = parseDate(coverage.comments_created_max);
  const postsRangeOk = Boolean(postsMin && postsMax && postsMin <= postsMax);
  const commentsRangeOk = Boolean(commentsMin && commentsMax && commentsMin <= commentsMax);
  const rangesOk = Boolean(postsRangeOk && commentsRangeOk);

  const totalsOk =
    (state.submolt || []).reduce((acc, r) => acc + (r.posts || 0), 0) > 0 &&
    (state.submolt || []).reduce((acc, r) => acc + (r.comments || 0), 0) > 0;

  const checks = [
    [
      "Co-ocurrencia top sin pares variantes",
      !hasVariantInTop,
      `${fmtNumber(cooccRows.length)} filas; variantes en top=${hasVariantInTop ? "si" : "no"}`,
    ],
    [
      "Pool de transmisión canónico",
      txPolicyMatch,
      `${fmtNumber(tx.pool.length)} filas; policy=${tx.policy}`,
    ],
    [
      "Shares de idioma normalizados",
      languageShareOk,
      `posts=${postShare.toFixed(3)} / comments=${commentShare.toFixed(3)}`,
    ],
    ["Rangos temporales válidos", rangesOk, `posts=${postsRangeOk ? "ok" : "fail"}, comments=${commentsRangeOk ? "ok" : "fail"}`],
    ["Volumen base no vacío", totalsOk, `${fmtNumber((state.submolt || []).length)} submolts activos`],
  ];

  body.innerHTML = checks
    .map(
      ([name, ok, detail]) => `<tr>
        <td>${escapeHtml(name)}</td>
        <td>${ok ? "PASS" : "FAIL"}</td>
        <td>${escapeHtml(detail)}</td>
      </tr>`
    )
    .join("");
}

function topSubmoltByActivity() {
  const sorted = [...(state.submolt || [])].sort(
    (a, b) => (b.posts || 0) + (b.comments || 0) - ((a.posts || 0) + (a.comments || 0))
  );
  return sorted[0] || null;
}

function topMemeByLifetime() {
  const sorted = [...(state.memeClass || [])].sort((a, b) => (b.lifetime_hours || 0) - (a.lifetime_hours || 0));
  return sorted[0] || null;
}

function dominantAct() {
  const acts = buildOntologySeries("act_", 12);
  if (!acts.length) return null;
  const total = acts.reduce((acc, r) => acc + (Number(r.count) || 0), 0);
  const top = acts[0];
  const share = total > 0 ? (Number(top.count) || 0) / total : 0;
  return { ...top, share };
}

function classifyInterference(score) {
  if (score === null || score === undefined || Number.isNaN(Number(score))) {
    return { label: "sin dato", tone: "neutral" };
  }
  const n = Number(score);
  if (n >= 0.25) return { label: "alto", tone: "danger" };
  if (n >= 0.12) return { label: "medio", tone: "warn" };
  return { label: "bajo", tone: "good" };
}

function mountExecutiveDashboard() {
  if (!document.getElementById("exec-meme")) return;

  const totalPosts = state.submolt.reduce((acc, r) => acc + (r.posts || 0), 0);
  const totalComments = state.submolt.reduce((acc, r) => acc + (r.comments || 0), 0);
  const totalVolume = totalPosts + totalComments;

  const topMeme = topMemeByLifetime();
  if (topMeme) {
    setText("exec-meme", topMeme.meme || "–");
    setText(
      "exec-meme-meta",
      `${fmtFloat(topMeme.lifetime_hours, 1)} hrs · ${fmtNumber(topMeme.submolts_touched)} submolts · burst ${fmtFloat(topMeme.burst_score, 1)}`
    );
    if ((topMeme.lifetime_hours || 0) >= 168) setChip("exec-meme-chip", "muy persistente", "danger");
    else if ((topMeme.lifetime_hours || 0) >= 72) setChip("exec-meme-chip", "persistente", "warn");
    else setChip("exec-meme-chip", "vida corta", "good");
  }

  const emb = state.embeddingsPostCommentSummary || state.embeddingsSummary || {};
  const crossRate = Number(emb.cross_submolt_rate);
  setText("exec-cross", fmtPercent(crossRate));
  setText("exec-cross-meta", `base: ${emb.model || "embeddings"} · matches ${fmtNumber(emb.total_matches)}`);
  if (crossRate >= 0.65) setChip("exec-cross-chip", "transversal alta", "danger");
  else if (crossRate >= 0.35) setChip("exec-cross-chip", "mixta", "warn");
  else setChip("exec-cross-chip", "local", "good");

  const topAct = dominantAct();
  if (topAct) {
    setText("exec-act", humanizeFeature(topAct.feature));
    setText("exec-act-meta", `share top acts ${fmtPercent(topAct.share)} · rate/doc ${fmtFloat(topAct.rate_per_doc, 3)}`);
    if (topAct.share >= 0.45) setChip("exec-act-chip", "hegemonico", "danger");
    else if (topAct.share >= 0.25) setChip("exec-act-chip", "dominante", "warn");
    else setChip("exec-act-chip", "distribuido", "good");
  }

  const topSub = topSubmoltByActivity();
  if (topSub) {
    const topVolume = (topSub.posts || 0) + (topSub.comments || 0);
    const topShare = totalVolume > 0 ? topVolume / totalVolume : 0;
    setText("exec-submolt", topSub.submolt || "–");
    setText(
      "exec-submolt-meta",
      `${fmtNumber(topSub.posts)} posts · ${fmtNumber(topSub.comments)} comentarios · ${fmtPercent(topShare)} del total`
    );
    if (topShare >= 0.08) setChip("exec-submolt-chip", "concentración alta", "danger");
    else if (topShare >= 0.04) setChip("exec-submolt-chip", "concentración media", "warn");
    else setChip("exec-submolt-chip", "concentración baja", "good");
  }

  const interAll = (state.interferenceSummary || []).find((r) => r.scope === "all");
  const interScore = interAll ? Number(interAll.avg_score) : null;
  const level = classifyInterference(interScore);
  setText("exec-interference", interScore === null ? "–" : fmtFloat(interScore, 3));
  setText(
    "exec-interference-meta",
    interAll
      ? `injection ${fmtPercent(interAll.injection_rate)} · disclaimers ${fmtPercent(interAll.disclaimer_rate)}`
      : "sin datos de interferencia para este snapshot"
  );
  setChip("exec-interference-chip", level.label, level.tone);

  const crossText = Number.isFinite(crossRate) ? fmtPercent(crossRate) : "–";
  const actText = topAct ? humanizeFeature(topAct.feature) : "n/d";
  const memeText = topMeme ? `${topMeme.meme} (${fmtFloat(topMeme.lifetime_hours, 1)} hrs)` : "n/d";
  setText("exec-surprise", `La difusión cross-submolt es ${crossText} y el acto dominante es "${actText}".`);
  setText("exec-implication", `Hay estilo discursivo estable con propagación transversal; meme más persistente: ${memeText}.`);
  setText("exec-noinfer", "No prueba causalidad ni manipulacion automática; marca donde conviene revisar evidencia cualitativa.");
}

function mountStrategicTLDR() {
  if (!document.getElementById("tldr-1")) return;
  const concentration = submoltConcentrationStats();
  const split = memeLayerStats();
  const embPc = state.embeddingsPostCommentSummary || {};
  const topAct = dominantAct();
  const hedgeRate = findOntologyRate("epistemic_hedge");
  const certaintyRate = findOntologyRate("epistemic_certainty");

  setText(
    "tldr-1",
    `Concentración alta: top 5 submolts acumulan ${fmtPercent(concentration.top5Share)} del volumen y el top 2% llega a ${fmtPercent(concentration.top2Share)}.`
  );

  const topInfra = [...split.technicalRows].sort((a, b) => (b.count || 0) - (a.count || 0))[0];
  const topCulture = [...split.culturalRows].sort((a, b) => (b.count || 0) - (a.count || 0))[0];
  setText(
    "tldr-2",
    `Memética en capas: infraestructura=${fmtPercent(split.technicalShare)} vs narrativa=${fmtPercent(split.culturalShare)}. Ejemplos: "${topInfra ? topInfra.meme : "n/d"}" y "${topCulture ? topCulture.meme : "n/d"}".`
  );

  const actLabel = topAct ? humanizeFeature(topAct.feature) : "n/d";
  setText(
    "tldr-3",
    `Estilo discursivo dominante: ${actLabel} con rate/doc ${fmtFloat(topAct ? topAct.rate_per_doc : null, 3)}; hedge=${fmtFloat(hedgeRate, 3)} vs certeza=${fmtFloat(certaintyRate, 3)}.`
  );

  setText(
    "tldr-4",
    `Transmisión transversal: ${fmtPercent(embPc.cross_submolt_rate)} de matches post→comentario cruzan submolts (similaridad media ${fmtFloat(embPc.mean_score, 3)}).`
  );

  const coverage = state.coverage || {};
  const createdMin = parseDate(coverage.posts_created_min || coverage.comments_created_min);
  const createdMax = parseDate(coverage.comments_created_max || coverage.posts_created_max);
  setText(
    "tldr-meta",
    `Snapshot ${fmtDate(createdMin)} — ${fmtDate(createdMax)} · no causalidad: lectura descriptiva y auditable.`
  );
}

function mountCoverageConcentration() {
  const topCtx = document.getElementById("concentration-top5-chart");
  const lorenzCtx = document.getElementById("concentration-lorenz-chart");
  if (!topCtx || !lorenzCtx) return;

  const concentration = submoltConcentrationStats();
  const top5Share = clamp01(concentration.top5Share);
  const restShare = clamp01(1 - top5Share);
  const gini = concentration.gini;

  setText("concentration-top5", fmtPercent(concentration.top5Share));
  setText("concentration-top2pct", fmtPercent(concentration.top2Share));
  setText("concentration-gini", fmtFloat(gini, 2));
  setText(
    "concentration-top5-note",
    `Top 5 submolts explican ${fmtPercent(concentration.top5Share)} del flujo total (posts + comentarios).`
  );
  setText(
    "concentration-lorenz-note",
    `Gini=${fmtFloat(gini, 2)}; a mayor valor, más desigual es la distribución de actividad entre submolts.`
  );

  if (concentrationTop5Chart) {
    concentrationTop5Chart.data.datasets[0].data = [top5Share, restShare];
    concentrationTop5Chart.update();
  } else {
    concentrationTop5Chart = new Chart(topCtx, {
      type: "doughnut",
      data: {
        labels: ["Top 5", "Resto"],
        datasets: [
          {
            data: [top5Share, restShare],
            backgroundColor: ["rgba(242, 95, 44, 0.78)", "rgba(15, 106, 180, 0.35)"],
            borderColor: ["rgba(242, 95, 44, 1)", "rgba(15, 106, 180, 0.65)"],
            borderWidth: 1,
          },
        ],
      },
      options: {
        responsive: true,
        cutout: "64%",
        plugins: {
          legend: { position: "bottom" },
          tooltip: {
            callbacks: {
              label: (context) => `${context.label}: ${fmtPercent(context.raw)}`,
            },
          },
        },
      },
    });
  }

  const lorenz = buildCumulativeCurve(concentration.volumes, { descending: false });
  const equality = [
    { x: 0, y: 0 },
    { x: 1, y: 1 },
  ];

  if (concentrationLorenzChart) {
    concentrationLorenzChart.data.datasets[0].data = lorenz;
    concentrationLorenzChart.update();
  } else {
    concentrationLorenzChart = new Chart(lorenzCtx, {
      type: "line",
      data: {
        datasets: [
          {
            label: "Curva observada",
            data: lorenz,
            parsing: false,
            borderColor: "rgba(31, 138, 112, 0.95)",
            backgroundColor: "rgba(31, 138, 112, 0.18)",
            fill: true,
            tension: 0.12,
            pointRadius: 0,
          },
          {
            label: "Igualdad perfecta",
            data: equality,
            parsing: false,
            borderColor: "rgba(94, 90, 85, 0.55)",
            borderDash: [6, 6],
            pointRadius: 0,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { position: "bottom" } },
        scales: {
          x: {
            type: "linear",
            min: 0,
            max: 1,
            ticks: {
              color: "#4f4b45",
              callback: (value) => `${Math.round(Number(value) * 100)}%`,
            },
            title: { display: true, text: "% acumulado de submolts" },
            grid: { color: "rgba(0,0,0,0.06)" },
          },
          y: {
            min: 0,
            max: 1,
            ticks: {
              color: "#4f4b45",
              callback: (value) => `${Math.round(Number(value) * 100)}%`,
            },
            title: { display: true, text: "% acumulado de volumen" },
            grid: { color: "rgba(0,0,0,0.06)" },
          },
        },
      },
    });
  }
}

function mountNarrativeLayers() {
  const totalPosts = state.submolt.reduce((acc, r) => acc + (r.posts || 0), 0);
  const totalComments = state.submolt.reduce((acc, r) => acc + (r.comments || 0), 0);
  const ratio = totalPosts > 0 ? totalComments / totalPosts : null;

  setText(
    "coverage-layer-1",
    `El snapshot tiene ${fmtNumber(totalPosts)} posts y ${fmtNumber(totalComments)} comentarios (${fmtFloat(ratio, 2)} comentarios por post).`
  );
  setText(
    "coverage-layer-2",
    "Patrón descriptivo: la relación comentarios/post resume cuánta actividad aparece como respuesta frente a publicación original."
  );
  setText(
    "coverage-layer-3",
    "No implica representatividad poblacional completa; es un snapshot operativo con límites de crawl."
  );

  const topSub = topSubmoltByActivity();
  if (topSub) {
    const totalVolume = totalPosts + totalComments;
    const topVolume = (topSub.posts || 0) + (topSub.comments || 0);
    const topShare = totalVolume > 0 ? topVolume / totalVolume : 0;
    setText(
      "submolts-layer-1",
      `El submolt "${topSub.submolt}" concentra ${fmtPercent(topShare)} del volumen visible.`
    );
    setText(
      "submolts-layer-2",
      "Patrón descriptivo: compara este share con el resto para medir concentración relativa entre comunidades."
    );
    setText(
      "submolts-layer-3",
      "Concentración de volumen no equivale automáticamente a centralidad de influencia ni calidad de conversación."
    );
  }

  const topMeme = topMemeByLifetime();
  const split = memeLayerStats();
  if (topMeme) {
    setText(
      "memetics-layer-1",
      `El meme más longevo es "${topMeme.meme}" con ${fmtFloat(topMeme.lifetime_hours, 1)} horas de vida.`
    );
    setText(
      "memetics-layer-2",
      `Patrón descriptivo: en candidatos top, infraestructura=${fmtPercent(split.technicalShare)} y narrativa=${fmtPercent(split.culturalShare)}.`
    );
    setText(
      "memetics-layer-3",
      "Frecuencia y burst no prueban origen ni intencionalidad sin contraste cualitativo."
    );
  }

  const topAct = dominantAct();
  if (topAct) {
    setText(
      "ontology-layer-1",
      `Predomina "${humanizeFeature(topAct.feature)}" (rate/doc ${fmtFloat(topAct.rate_per_doc, 3)}).`
    );
    setText(
      "ontology-layer-2",
      "Patrón descriptivo: usa este rate/doc para comparar distribución de actos y marcadores epistémicos por submolt."
    );
    setText(
      "ontology-layer-3",
      "El mapa PCA no es causal ni temático; es una proyección estructural de estilo discursivo."
    );
  }

  const emb = state.embeddingsPostCommentSummary || state.embeddingsSummary || {};
  setText(
    "transmission-layer-1",
    `La transmisión post→comentario cruza submolts en ${fmtPercent(emb.cross_submolt_rate)} con similaridad media ${fmtFloat(emb.mean_score, 3)}.`
  );
  setText(
    "transmission-layer-2",
    "Patrón descriptivo: esta tasa indica que fracción de pares similares cae en submolts distintos."
  );
  setText(
    "transmission-layer-3",
    "Similaridad alta no prueba copia directa ni coordinación intencional; exige contraste temporal y ejemplos cualitativos."
  );
}

function mountSummary() {
  const totalPosts = state.submolt.reduce((acc, r) => acc + (r.posts || 0), 0);
  const totalComments = state.submolt.reduce((acc, r) => acc + (r.comments || 0), 0);
  const totalSubmolts = state.submolt.length;
  const totalRuns = new Set(state.diffusion.map((r) => r.run_id)).size;
  const totalAuthors = state.authors.length;

  setText("total-posts", fmtNumber(totalPosts));
  setText("total-comments", fmtNumber(totalComments));
  setText("total-submolts", fmtNumber(totalSubmolts));
  setText("total-authors", state.authorsLoaded ? fmtNumber(totalAuthors) : "cargando...");
  setText("total-runs", fmtNumber(totalRuns));

  const coverage = state.coverage || {};
  const createdMins = [coverage.posts_created_min, coverage.comments_created_min]
    .map(parseDate)
    .filter(Boolean);
  const createdMaxs = [coverage.posts_created_max, coverage.comments_created_max]
    .map(parseDate)
    .filter(Boolean);
  const createdMin = createdMins.length ? new Date(Math.min(...createdMins)) : null;
  const createdMax = createdMaxs.length ? new Date(Math.max(...createdMaxs)) : null;
  setText("coverage-range", `${fmtDate(createdMin)} — ${fmtDate(createdMax)}`);
}

function mountCoverageQuality() {
  const coverage = state.coverage || {};
  setText("ratio-posts-comments", fmtFloat(coverage.post_comment_ratio, 2));
  setText("dup-posts", fmtNumber(coverage.posts_duplicates));
  setText("dup-comments", fmtNumber(coverage.comments_duplicates));
  setText("range-posts", `${fmtDate(parseDate(coverage.posts_created_min))} — ${fmtDate(parseDate(coverage.posts_created_max))}`);
  setText(
    "range-comments",
    `${fmtDate(parseDate(coverage.comments_created_min))} — ${fmtDate(parseDate(coverage.comments_created_max))}`
  );
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

function mountTransmissionTranslation() {
  const leadEl = document.getElementById("transmission-translation-lead");
  if (!leadEl) return;
  const subEl = document.getElementById("transmission-translation-sub");

  const emb = state.embeddingsSummary || {};
  const embPc = state.embeddingsPostCommentSummary || {};
  const cross = Number(embPc.cross_submolt_rate);
  const postPostMean = Number(emb.mean_score);
  const postCommentMean = Number(embPc.mean_score);
  const similarityDrop =
    Number.isFinite(postPostMean) && Number.isFinite(postCommentMean) ? postPostMean - postCommentMean : null;
  const echoRetention =
    Number.isFinite(postPostMean) && postPostMean > 0 && Number.isFinite(postCommentMean)
      ? postCommentMean / postPostMean
      : null;

  leadEl.textContent =
    `La narrativa se replica más alla de comunidades locales: ${fmtPercent(cross)} de matches post→comentario cruza submolts.`;
  if (subEl) {
    subEl.textContent =
      `Lectura ejecutiva: post-post=${fmtFloat(postPostMean, 3)} vs post→comentario=${fmtFloat(postCommentMean, 3)} ` +
      `(caida ${fmtFloat(similarityDrop, 3)}; retencion ${fmtPercent(echoRetention)}).`;
  }
}

let languageChart;
function mountLanguageChart() {
  const ctx = document.getElementById("language-chart");
  if (!ctx) return;

  const posts = state.language
    .filter((r) => r.scope === "posts")
    .filter((r) => (state.filters.hideLanguageEn ? r.lang !== "en" : true));
  const comments = state.language
    .filter((r) => r.scope === "comments")
    .filter((r) => (state.filters.hideLanguageEn ? r.lang !== "en" : true));

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

  if (languageChart) {
    languageChart.data.labels = langs;
    languageChart.data.datasets[0].data = langs.map((l) => postMap[l] || 0);
    languageChart.data.datasets[1].data = langs.map((l) => commentMap[l] || 0);
    languageChart.update();
    return;
  }

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
  const ctx = document.getElementById("submolt-chart");
  if (!ctx) return;

  const sorted = [...state.submolt]
    .filter((r) => (state.filters.hideSubmoltGeneral ? String(r.submolt || "").toLowerCase() !== "general" : true))
    .sort((a, b) => (b[metric] || 0) - (a[metric] || 0));
  const top = sorted.slice(0, 15);

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
  if (!tableBody) return;
  const rows = [...state.submolt]
    .sort((a, b) => (b.posts || 0) + (b.comments || 0) - ((a.posts || 0) + (a.comments || 0)))
    .slice(0, LIMITS.submoltTable);
  const maxVolume = rows.reduce((acc, r) => Math.max(acc, (r.posts || 0) + (r.comments || 0)), 0);
  const totalVolume = rows.reduce((acc, r) => acc + (r.posts || 0) + (r.comments || 0), 0);
  tableBody.innerHTML = rows
    .map(
      (r) => `<tr>
        <td>${r.submolt}</td>
        <td>${fmtNumber(r.posts)}</td>
        <td>${fmtNumber(r.comments)}</td>
        <td class="cell-meter">${renderMeter((r.posts || 0) + (r.comments || 0), maxVolume, fmtPercent(((r.posts || 0) + (r.comments || 0)) / Math.max(totalVolume, 1)))}</td>
        <td>${fmtFloat(r.mean_upvotes)}</td>
        <td>${fmtNumber(r.runs_seen)}</td>
      </tr>`
    )
    .join("");
}

let memeCandidatesChart;
let memeScatterChart;

function mountMemeLayerSplit() {
  const chartEl = document.getElementById("meme-layer-chart");
  const infraShareEl = document.getElementById("meme-infra-share");
  if (!chartEl || !infraShareEl) return;

  const split = memeLayerStats();
  const infraShare = clamp01(split.technicalShare);
  const cultureShare = clamp01(split.culturalShare);

  setText("meme-infra-share", fmtPercent(split.technicalShare));
  setText("meme-culture-share", fmtPercent(split.culturalShare));
  setText("meme-infra-count", `${fmtNumber(split.technicalCount)} menciones agregadas`);
  setText("meme-culture-count", `${fmtNumber(split.culturalCount)} menciones agregadas`);

  const renderList = (id, rows, total) => {
    const el = document.getElementById(id);
    if (!el) return;
    if (!rows.length) {
      el.innerHTML = "<li>Sin datos</li>";
      return;
    }
    el.innerHTML = rows
      .slice(0, 5)
      .map((r) => {
        const count = Number(r.count) || 0;
        const localShare = total > 0 ? count / total : 0;
        return `<li><span>${escapeHtml(r.meme)}</span><strong>${fmtPercent(localShare)}</strong></li>`;
      })
      .join("");
  };

  const topInfra = [...split.technicalRows].sort((a, b) => (b.count || 0) - (a.count || 0));
  const topCulture = [...split.culturalRows].sort((a, b) => (b.count || 0) - (a.count || 0));
  renderList("meme-infra-top", topInfra, split.technicalCount);
  renderList("meme-culture-top", topCulture, split.culturalCount);

  if (memeLayerChart) {
    memeLayerChart.data.datasets[0].data = [infraShare, cultureShare];
    memeLayerChart.update();
    return;
  }

  memeLayerChart = new Chart(chartEl, {
    type: "bar",
    data: {
      labels: ["Infraestructura", "Cultura narrativa"],
      datasets: [
        {
          label: "share",
          data: [infraShare, cultureShare],
          backgroundColor: ["rgba(15, 106, 180, 0.68)", "rgba(31, 138, 112, 0.68)"],
          borderRadius: 10,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => `share: ${fmtPercent(ctx.raw)}`,
          },
        },
      },
      scales: {
        x: { ticks: { color: "#4f4b45" }, grid: { display: false } },
        y: {
          min: 0,
          max: 1,
          ticks: {
            color: "#4f4b45",
            callback: (value) => `${Math.round(Number(value) * 100)}%`,
          },
          grid: { color: "rgba(0,0,0,0.06)" },
        },
      },
    },
  });
}

function mountMemeCharts() {
  const candCtx = document.getElementById("meme-candidates-chart");
  const scatterCtx = document.getElementById("meme-scatter-chart");
  if (!candCtx || !scatterCtx) return;

  const candidates = [...state.memeCandidates]
    .sort((a, b) => (b.count || 0) - (a.count || 0))
    .slice(0, 12);

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
  if (!tableBody) return;
  const rows = [...state.memeClass]
    .sort((a, b) => (b.lifetime_hours || 0) - (a.lifetime_hours || 0))
    .slice(0, LIMITS.memeSurvivalTable);
  const maxTouches = rows.reduce((acc, r) => Math.max(acc, Number(r.submolts_touched) || 0), 0);
  tableBody.innerHTML = rows
    .map(
      (r) => `<tr>
        <td>${r.meme}</td>
        <td>${fmtFloat(r.lifetime_hours, 1)}</td>
        <td class="cell-meter">${renderMeter(r.submolts_touched || 0, maxTouches)}</td>
        <td>${fmtFloat(r.burst_score, 1)}</td>
        <td>${r.class || "–"}</td>
      </tr>`
    )
    .join("");
}

function mountMemeBurstTable() {
  const tableBody = document.querySelector("#meme-burst-table tbody");
  if (!tableBody) return;
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
    .slice(0, LIMITS.memeBurstTable);

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

function findOntologyRate(feature) {
  const row = (state.ontologySummary || []).find((r) => r.scope === "all" && r.feature === feature);
  return row ? Number(row.rate_per_doc) : null;
}

function mountOntologyInterpretation() {
  const assertionRate = findOntologyRate("act_assertion");
  const hedgeRate = findOntologyRate("epistemic_hedge");
  const evidenceRate = findOntologyRate("epistemic_evidence");
  const certaintyRate = findOntologyRate("epistemic_certainty");

  const set = (id, value) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = value;
  };

  set("onto-rate-assertion", fmtFloat(assertionRate, 3));
  set("onto-rate-hedge", fmtFloat(hedgeRate, 3));
  set("onto-rate-evidence", fmtFloat(evidenceRate, 3));
  set("onto-rate-certainty", fmtFloat(certaintyRate, 3));

  const readout = document.getElementById("onto-rate-readout");
  if (readout) {
    if ([assertionRate, hedgeRate, evidenceRate, certaintyRate].some((v) => v === null || Number.isNaN(v))) {
      readout.textContent = "No hay suficientes datos para leer la tension afirmación/hedge/evidencia/certeza.";
    } else {
      readout.textContent = `Lectura cuantitativa global: afirmación=${fmtFloat(assertionRate, 3)}, hedge=${fmtFloat(hedgeRate, 3)}, evidencia=${fmtFloat(evidenceRate, 3)}, certeza=${fmtFloat(certaintyRate, 3)}.`;
    }
  }

  const shape = document.getElementById("onto-pca-shape");
  if (!shape) return;

  const rows = [...(state.ontologyEmbedding2d || [])]
    .sort((a, b) => (b.doc_count || 0) - (a.doc_count || 0))
    .slice(0, 250);

  if (rows.length < 12) {
    shape.textContent = "No hay suficientes submolts para evaluar forma global del mapa (clusters vs gradiente).";
    return;
  }

  const meanX = rows.reduce((acc, r) => acc + (Number(r.x) || 0), 0) / rows.length;
  const meanY = rows.reduce((acc, r) => acc + (Number(r.y) || 0), 0) / rows.length;

  const distances = rows
    .map((r) => {
      const dx = (Number(r.x) || 0) - meanX;
      const dy = (Number(r.y) || 0) - meanY;
      return Math.sqrt(dx * dx + dy * dy);
    })
    .sort((a, b) => a - b);

  const quantile = (sorted, q) => {
    if (!sorted.length) return null;
    const pos = (sorted.length - 1) * q;
    const base = Math.floor(pos);
    const rest = pos - base;
    if (sorted[base + 1] !== undefined) {
      return sorted[base] + rest * (sorted[base + 1] - sorted[base]);
    }
    return sorted[base];
  };

  const p50 = quantile(distances, 0.5);
  const p90 = quantile(distances, 0.9);
  const ratio = p50 && p50 > 0 ? p90 / p50 : null;

  let diagnostic = "nube continua con gradientes";
  if (ratio !== null && ratio >= 2.2) diagnostic = "nube central con colas/outliers (clusters potenciales)";
  if (ratio !== null && ratio >= 2.8) diagnostic = "separación fuerte: clusters más diferenciados";

  shape.textContent = `Forma del mapa (top ${rows.length} submolts): mediana_dist=${fmtFloat(p50, 2)}, p90_dist=${fmtFloat(p90, 2)}, razon p90/p50=${fmtFloat(ratio, 2)} -> ${diagnostic}.`;
}

function findOntologySubmoltProfile(name) {
  const rows = state.ontologySubmoltFull || [];
  const needle = String(name || "").trim().toLowerCase();
  if (!needle) return null;
  const exact = rows.find((r) => String(r.submolt || "").trim().toLowerCase() === needle);
  if (exact) return exact;
  const prefixed = rows.find((r) => String(r.submolt || "").trim().toLowerCase().startsWith(needle));
  return prefixed || null;
}

function ontologyRateByFeature(row, feature) {
  const docs = Number(row && row.doc_count) || 0;
  const count = Number(row && row[feature]) || 0;
  if (docs <= 0) return 0;
  return count / docs;
}

function mountOntologyCompare() {
  const chartEl = document.getElementById("ontology-compare-chart");
  if (!chartEl) return;

  const agents = findOntologySubmoltProfile("agents");
  const philosophy = findOntologySubmoltProfile("philosophy");
  const noteEl = document.getElementById("ontology-compare-note");

  if (!agents || !philosophy) {
    if (noteEl) noteEl.textContent = "No hay filas suficientes para comparar submolts agents vs philosophy.";
    return;
  }

  const features = [
    { key: "act_assertion", label: "Afirmación" },
    { key: "epistemic_evidence", label: "Evidencia" },
    { key: "epistemic_hedge", label: "Hedge" },
    { key: "act_judgment", label: "Juicio" },
    { key: "act_question_mark", label: "Pregunta" },
  ];

  const agentsRates = features.map((f) => ontologyRateByFeature(agents, f.key));
  const philosophyRates = features.map((f) => ontologyRateByFeature(philosophy, f.key));

  if (ontologyCompareChart) {
    ontologyCompareChart.data.labels = features.map((f) => f.label);
    ontologyCompareChart.data.datasets[0].data = agentsRates;
    ontologyCompareChart.data.datasets[1].data = philosophyRates;
    ontologyCompareChart.update();
  } else {
    ontologyCompareChart = new Chart(chartEl, {
      type: "bar",
      data: {
        labels: features.map((f) => f.label),
        datasets: [
          {
            label: "agents",
            data: agentsRates,
            backgroundColor: "rgba(15, 106, 180, 0.65)",
            borderRadius: 8,
          },
          {
            label: "philosophy",
            data: philosophyRates,
            backgroundColor: "rgba(242, 95, 44, 0.62)",
            borderRadius: 8,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { position: "bottom" } },
        scales: {
          x: { ticks: { color: "#4f4b45" }, grid: { display: false } },
          y: { ticks: { color: "#4f4b45" }, grid: { color: "rgba(0,0,0,0.06)" } },
        },
      },
    });
  }

  if (noteEl) {
    noteEl.textContent =
      `agents: afirmación ${fmtFloat(agentsRates[0], 3)} y evidencia ${fmtFloat(agentsRates[1], 3)}; ` +
      `philosophy: hedge ${fmtFloat(philosophyRates[2], 3)} y juicio ${fmtFloat(philosophyRates[3], 3)}.`;
  }
}

function mountOntologyCharts() {
  const actsEl = document.getElementById("ontology-acts-chart");
  const moodsEl = document.getElementById("ontology-moods-chart");
  const epistemicEl = document.getElementById("ontology-epistemic-chart");
  if (!actsEl || !moodsEl || !epistemicEl) return;

  const acts = buildOntologySeries("act_", 8);
  const moods = buildOntologySeries("mood_", 8);
  const epistemic = buildOntologySeries("epistemic_", 6);

  ontologyActsChart = new Chart(actsEl, {
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

  ontologyMoodsChart = new Chart(moodsEl, {
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

  ontologyEpistemicChart = new Chart(epistemicEl, {
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
  if (!pairsBody) return;

  const acts = buildOntologySeries("act_", 12);
  if (actsBody) {
    actsBody.innerHTML = acts
      .map(
        (r) => `<tr>
          <td>${humanizeFeature(r.feature)}</td>
          <td>${fmtNumber(r.count)}</td>
          <td>${fmtFloat(r.rate_per_doc, 3)}</td>
        </tr>`
      )
      .join("");
  }

  const concepts = [...state.ontologyConcepts].slice(0, LIMITS.ontologyConceptsTable);
  if (conceptsBody) {
    conceptsBody.innerHTML = concepts
      .map(
        (r) => `<tr>
          <td>${r.concept}</td>
          <td>${fmtNumber(r.doc_count ?? r.count)}</td>
          <td>${fmtPercent(r.share)}</td>
        </tr>`
      )
      .join("");
  }

  const pairs = [...state.ontologyCooccurrence]
    .filter((r) => !isVariantPair(r.concept_a, r.concept_b))
    .slice(0, LIMITS.ontologyCooccurrenceTable);
  pairsBody.innerHTML = pairs
    .map(
      (r) => `<tr>
        <td>${r.concept_a}</td>
        <td>${r.concept_b}</td>
        <td>${fmtNumber(r.count)}</td>
      </tr>`
    )
    .join("");
  mountActiveFiltersSummary();
  mountCoherenceCheck();
}

let ontologyMapChart;
function mountOntologyMap() {
  const ctx = document.getElementById("ontology-map-chart");
  if (!ctx) return;

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

function mountTransmissionTable() {
  const select = document.getElementById("transmission-submolt");
  const search = document.getElementById("transmission-search");
  const body = document.querySelector("#transmission-table tbody");
  if (!select || !search || !body) return;
  const sourceRows = (state.transmissionPolicy && state.transmissionPolicy.pool) || [];

  const submolts = ["all", ...new Set(sourceRows.map((r) => r.submolt || "unknown"))].sort();
  select.innerHTML = submolts.map((s) => `<option value="${s}">${s}</option>`).join("");

  const render = () => {
    const sub = select.value;
    const term = search.value.toLowerCase();
    const rows = sourceRows
      .filter((r) => (sub === "all" ? true : (r.submolt || "unknown") === sub))
      .filter((r) => String(r.text || "").toLowerCase().includes(term))
      .slice(0, 80);

    body.innerHTML = rows
      .map(
        (r) => `<tr>
          <td>${r.source}</td>
          <td>${r.submolt || "unknown"}</td>
          <td>${String(r.created_at || "").slice(0, 16).replace("T", " ")}</td>
          <td class="cell-text">${escapeHtml(r.text)}</td>
        </tr>`
      )
      .join("");
    state.transmissionVisibleCount = rows.length;
    mountActiveFiltersSummary();
  };

  select.addEventListener("change", render);
  search.addEventListener("input", render);
  render();
}

function buildSociologyFallback() {
  const concentration = submoltConcentrationStats();
  const split = memeLayerStats();
  const embPc = state.embeddingsPostCommentSummary || {};
  const coverage = state.coverage || {};
  const topAct = dominantAct();
  const assertion = findOntologyRate("act_assertion");
  const evidence = findOntologyRate("epistemic_evidence");
  const certainty = findOntologyRate("epistemic_certainty");
  const top5 = fmtPercent(concentration.top5Share);
  const cross = fmtPercent(embPc.cross_submolt_rate);
  const actLabel = topAct ? humanizeFeature(topAct.feature) : "n/d";

  return {
    generated_at: new Date().toISOString(),
    summary: {
      thesis:
        `Lectura automática: red con concentración alta (${top5} en top 5), ` +
        `estilo dominante "${actLabel}" y difusión transversal (${cross} cross-submolt en post→coment).`,
      snapshot: {
        posts_total: Number(coverage.posts_total || 0),
        comments_total: Number(coverage.comments_total || 0),
        posts_min: coverage.posts_created_min || "n/d",
        posts_max: coverage.posts_created_max || "n/d",
      },
      key_metrics: {
        top5_share: concentration.top5Share,
        top2_share: concentration.top2Share,
        infra_share: split.technicalShare,
        cross_submolt_post_comment: Number(embPc.cross_submolt_rate),
        assertion_rate_per_doc: assertion,
        evidence_rate_per_doc: evidence,
        certainty_rate_per_doc: certainty,
      },
    },
    modules: [
      {
        id: "1.1",
        title: "Actividad y cobertura",
        interpretation:
          "El volumen y la ventana temporal delimitan qué tan estructural o episódica puede ser la lectura.",
        how_to_read: [
          "Ventanas cortas capturan eventos; ventanas largas capturan hábitos.",
          "Comparar runs evita confundir cambios de ingesta con cambios culturales.",
        ],
        not_meaning: ["No es censo total de plataforma; es snapshot operativo."],
        auditable_questions: ["¿Si repites el pipeline, se conservan estos agregados?"],
      },
      {
        id: "1.2",
        title: "Concentración de atención",
        interpretation: `Top 5 submolts concentran ${top5}; la red no distribuye volumen de forma uniforme.`,
        how_to_read: [
          "Curva acumulada empinada implica oligopolio de atención.",
          "Gini creciente entre snapshots indica centralización creciente.",
        ],
        not_meaning: ["Volumen alto no equivale a calidad."],
        auditable_questions: ["¿Se mantiene la concentración al mirar solo comentarios?"],
      },
      {
        id: "2.1",
        title: "Infraestructura vs narrativa",
        interpretation:
          `Infraestructura=${fmtPercent(split.technicalShare)} vs narrativa=${fmtPercent(split.culturalShare)}.`,
        how_to_read: [
          "Suba de infraestructura sugiere modo operativo.",
          "Suba de narrativa sugiere modo de significación identitaria.",
        ],
        not_meaning: ["Infraestructura no es ruido; define gramática de participación."],
        auditable_questions: ["¿La narrativa cruza submolts o queda localizada?"],
      },
      {
        id: "4.1",
        title: "Transmisión semántica",
        interpretation:
          `Cross-submolt post→comentario: ${cross}. Similaridad media: ${fmtFloat(embPc.mean_score, 3)}.`,
        how_to_read: [
          "Cross alto sugiere marcos que viajan entre comunidades.",
          "Comparar con threshold sensitivity para separar ruido de señal robusta.",
        ],
        not_meaning: ["Similaridad no implica coordinación intencional."],
        auditable_questions: ["¿Dónde cae el codo natural al subir threshold?"],
      },
      {
        id: "5.1",
        title: "Centralidad de red",
        interpretation:
          "Centralidad mide estructura de circulación (hubs y brokers), no calidad deliberativa.",
        how_to_read: [
          "PageRank alto = hub; betweenness alto = puente entre tribus.",
          "Reciprocidad baja sugiere broadcasting.",
        ],
        not_meaning: ["Centralidad no es moralidad."],
        auditable_questions: ["¿Los brokers son pocos o distribuidos?"],
      },
      {
        id: "6.1",
        title: "Auditoría y contrato",
        interpretation:
          "La lectura sociológica solo es defendible si cada claim traza a artefactos reproducibles.",
        how_to_read: [
          "Todo gráfico debe enlazar a su derivado.",
          "Separar observación de inferencia y de límites.",
        ],
        not_meaning: ["Trazabilidad no elimina sesgo; lo vuelve visible."],
        auditable_questions: ["¿Cada claim tiene fuente, filtro, transformación y límite explicitado?"],
      },
    ],
  };
}

function renderSociologyList(items) {
  const clean = (items || []).filter(Boolean);
  if (!clean.length) return "<div class=\"sociology-empty\">Sin items.</div>";
  return `<ul class="sociology-list">${clean.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function renderSociologyParagraphs(items) {
  const clean = (items || []).filter(Boolean);
  if (!clean.length) return "";
  return clean.map((item) => `<p>${escapeHtml(item)}</p>`).join("");
}

function renderSociologyPcaBody(mod) {
  const introText = mod.pca_case_intro || mod.what_it_is || mod.interpretation || "Sin interpretación.";
  const intro = `<p>${escapeHtml(introText)}</p>${mod.interpretation ? `<p>${escapeHtml(mod.interpretation)}</p>` : ""}`;

  const structuralBlocks = (mod.pca_structural || [])
    .filter(Boolean)
    .map((block) => {
      const label = escapeHtml(block.label || "Bloque");
      const body = escapeHtml(block.body || "");
      const implications = renderSociologyList(block.implications || []);
      return `<div class="sociology-item-subblock">
        <div class="sociology-item-sublabel">${label}</div>
        <p>${body}</p>
        ${implications}
      </div>`;
    })
    .join("");

  const deepReading = renderSociologyParagraphs(mod.pca_deep_reading || []);
  const systemReading = mod.pca_system_reading ? `<p>${escapeHtml(mod.pca_system_reading)}</p>` : "";
  const limits = renderSociologyList([
    ...(mod.pca_not_conclusions || []),
    ...(mod.not_meaning || []),
  ]);
  const whyThisMatters = mod.pca_why_this_matters ? `<p>${escapeHtml(mod.pca_why_this_matters)}</p>` : "";
  const audit = renderSociologyList(mod.auditable_questions || []);

  return `<div class="sociology-item-block">
    <div class="sociology-item-label">1) Primero: qué es este PCA en este caso</div>
    ${intro}
  </div>
  <div class="sociology-item-block">
    <div class="sociology-item-label">Qué está mostrando estructuralmente</div>
    ${structuralBlocks || "<div class=\"sociology-empty\">Sin lectura estructural.</div>"}
  </div>
  <div class="sociology-item-block">
    <div class="sociology-item-label">Lectura sociológica profunda</div>
    ${deepReading || "<div class=\"sociology-empty\">Sin lectura profunda.</div>"}
  </div>
  <div class="sociology-item-block">
    <div class="sociology-item-label">Lo que dice del sistema como organismo</div>
    ${systemReading || "<div class=\"sociology-empty\">Sin lectura de sistema.</div>"}
  </div>
  <div class="sociology-item-block">
    <div class="sociology-item-label">Lo que NO puedes concluir</div>
    ${limits}
  </div>
  <div class="sociology-item-block">
    <div class="sociology-item-label">Lo realmente interesante</div>
    ${whyThisMatters || "<div class=\"sociology-empty\">Sin cierre interpretativo.</div>"}
  </div>
  <div class="sociology-item-block">
    <div class="sociology-item-label">Preguntas auditables</div>
    ${audit}
  </div>`;
}

function renderSociologyModuleBody(mod) {
  if (String(mod.id || "") === "3.4") {
    return renderSociologyPcaBody(mod);
  }

  const what = mod.what_it_is ? `<p>${escapeHtml(mod.what_it_is)}</p>` : "<div class=\"sociology-empty\">Sin definición.</div>";
  const why = mod.why_it_matters
    ? `<p>${escapeHtml(mod.why_it_matters)}</p>`
    : "<div class=\"sociology-empty\">Sin justificación explícita.</div>";
  const interpretation = mod.interpretation
    ? `<p>${escapeHtml(mod.interpretation)}</p>`
    : "<div class=\"sociology-empty\">Sin interpretación.</div>";
  const termsItems = (mod.terms || []).filter(Boolean);
  const howItems = (mod.how_to_read || []).filter(Boolean);
  const misreadsItems = (mod.common_misreads || []).filter(Boolean);
  const notMeaningItems = (mod.not_meaning || []).filter(Boolean);
  const auditItems = (mod.auditable_questions || []).filter(Boolean);
  const terms = termsItems.length ? renderSociologyList(termsItems) : "";
  const how = renderSociologyList(howItems);
  const limits = renderSociologyList([...misreadsItems, ...notMeaningItems]);
  const audit = renderSociologyList(auditItems);
  return `<div class="sociology-item-block">
    <div class="sociology-item-label">Qué es en este caso</div>
    ${what}
  </div>
  <div class="sociology-item-block">
    <div class="sociology-item-label">Por qué importa</div>
    ${why}
  </div>
  <div class="sociology-item-block">
    <div class="sociology-item-label">Interpretación completa</div>
    ${interpretation}
  </div>
  ${
    terms
      ? `<div class="sociology-item-block">
    <div class="sociology-item-label">Términos clave en simple</div>
    ${terms}
  </div>`
      : ""
  }
  <div class="sociology-item-block">
    <div class="sociology-item-label">Cómo leerlo paso a paso</div>
    ${how}
  </div>
  <div class="sociology-item-block">
    <div class="sociology-item-label">Qué NO significa (para no sobreleer)</div>
    ${limits}
  </div>
  <div class="sociology-item-block">
    <div class="sociology-item-label">Preguntas auditables</div>
    ${audit}
  </div>`;
}

function renderSociologyModulePanel(mod) {
  const id = escapeHtml(mod.id || "");
  const title = escapeHtml(mod.title || "Módulo");
  const heading = id ? `${id} · ${title}` : title;
  return `<article class="card sociology-panel">
    <h4 class="sociology-panel-title">${heading}</h4>
    <div class="sociology-item-body">
      ${renderSociologyModuleBody(mod)}
    </div>
  </article>`;
}

function renderSociologyModuleStack(modules) {
  const clean = (modules || []).filter(Boolean);
  if (!clean.length) return "";
  return `<div class="sociology-module-stack">${clean.map((mod) => renderSociologyModulePanel(mod)).join("")}</div>`;
}

function fmtSociologyDate(rawValue) {
  if (!rawValue) return "n/d";
  const parsed = parseDate(rawValue);
  return parsed ? fmtDate(parsed) : String(rawValue);
}

function renderSociologySummary(payload) {
  const summary = payload.summary || {};
  const key = summary.key_metrics || {};
  const snap = summary.snapshot || {};
  const generated = payload.generated_at ? fmtSociologyDate(payload.generated_at) : "n/d";
  const postsMin = fmtSociologyDate(snap.posts_min);
  const postsMax = fmtSociologyDate(snap.posts_max);
  return `<article class="card transmission-translation sociology-summary-card">
    <div class="table-header">
      Lectura sociológica automática
      <span class="info-tip" data-tip="Generado desde data/derived/public_sociology_interpretation.json">i</span>
    </div>
    <p class="translation-lead">${escapeHtml(summary.thesis || "Sin tesis automática disponible.")}</p>
    <p class="translation-sub">Generado: ${escapeHtml(generated)} · Snapshot posts ${escapeHtml(postsMin)} -> ${escapeHtml(postsMax)}</p>
    <div class="card-grid" style="margin-top: 12px;">
      <div class="card">
        <div class="card-label">Top 5 (volumen)</div>
        <div class="card-value">${fmtPercent(key.top5_share)}</div>
      </div>
      <div class="card">
        <div class="card-label">Top 2% (volumen)</div>
        <div class="card-value">${fmtPercent(key.top2_share)}</div>
      </div>
      <div class="card">
        <div class="card-label">Cross-submolt post→coment</div>
        <div class="card-value">${fmtPercent(key.cross_submolt_post_comment)}</div>
      </div>
      <div class="card">
        <div class="card-label">Infraestructura memética</div>
        <div class="card-value">${fmtPercent(key.infra_share)}</div>
      </div>
    </div>
  </article>`;
}

function renderSociologyCompact(mod) {
  const title = escapeHtml(mod.title || "Análisis");
  const what =
    mod.what_it_is ||
    mod.pca_case_intro ||
    "Sin descripción disponible para este bloque.";
  const interpretation = mod.interpretation || "Sin interpretación disponible.";
  const analysis =
    mod.why_it_matters ||
    mod.pca_why_this_matters ||
    mod.pca_system_reading ||
    "Sin análisis disponible.";
  const how = Array.isArray(mod.how_to_read) && mod.how_to_read.length ? mod.how_to_read[0] : "";

  return `<article class="analysis-inline-card">
    <div class="analysis-inline-title">${title}</div>
    <p><strong>Qué muestra:</strong> ${escapeHtml(what)}</p>
    <p><strong>Interpretación:</strong> ${escapeHtml(interpretation)}</p>
    <p><strong>Análisis:</strong> ${escapeHtml(analysis)}</p>
    ${how ? `<p><strong>Cómo leer:</strong> ${escapeHtml(how)}</p>` : ""}
  </article>`;
}

function mountSociologyPanel() {
  const payload = state.sociology || buildSociologyFallback();
  const modules = Array.isArray(payload.modules) ? payload.modules : [];
  const byId = new Map(modules.map((mod) => [String(mod.id || "").trim(), mod]));
  const used = new Set();

  const sections = [
    {
      rootId: "sociology-inline-coverage",
      title: "Interpretación sociológica de cobertura y concentración",
      moduleIds: ["1.1", "1.2"],
      includeSummary: true,
    },
    {
      rootId: "sociology-inline-language",
      title: "Interpretación sociológica de idioma",
      moduleIds: ["1.3"],
    },
    {
      rootId: "sociology-inline-memetics",
      title: "Interpretación sociológica de memética",
      moduleIds: ["2.1", "2.2"],
    },
    {
      rootId: "sociology-inline-ontology-31",
      moduleIds: ["3.1"],
      compact: true,
    },
    {
      rootId: "sociology-inline-ontology-32",
      moduleIds: ["3.2"],
      compact: true,
    },
    {
      rootId: "sociology-inline-ontology-33",
      moduleIds: ["3.3"],
      compact: true,
    },
    {
      rootId: "sociology-inline-ontology-34",
      moduleIds: ["3.4"],
      compact: true,
    },
    {
      rootId: "sociology-inline-transmission",
      title: "Interpretación sociológica de transmisión",
      moduleIds: ["4.1", "4.2", "4.3", "4.4"],
    },
    {
      rootId: "sociology-inline-network",
      title: "Interpretación sociológica de red",
      moduleIds: ["5.1"],
    },
    {
      rootId: "sociology-inline-authors",
      title: "Interpretación sociológica de autores",
      moduleIds: ["5.2"],
    },
    {
      rootId: "sociology-inline-method",
      title: "Interpretación sociológica de trazabilidad",
      moduleIds: ["6.1", "6.2"],
    },
  ];

  sections.forEach((section) => {
    const root = document.getElementById(section.rootId);
    if (!root) return;

    const selected = section.moduleIds
      .map((id) => {
        const mod = byId.get(id);
        if (mod) used.add(id);
        return mod;
      })
      .filter(Boolean);

    const blocks = [];
    if (section.includeSummary) {
      blocks.push(renderSociologySummary(payload));
    }
    if (selected.length && section.compact) {
      blocks.push(selected.map((mod) => renderSociologyCompact(mod)).join(""));
    } else if (selected.length) {
      blocks.push(`<div class="sociology-inline-title">${escapeHtml(section.title)}</div>`);
      blocks.push(renderSociologyModuleStack(selected));
    }

    root.innerHTML = blocks.join("");
    root.style.display = blocks.length ? "" : "none";
  });

  const leftovers = modules.filter((mod) => !used.has(String(mod.id || "").trim()));
  if (!leftovers.length) return;
  const extraRoot = document.getElementById("sociology-inline-method");
  if (!extraRoot) return;
  extraRoot.style.display = "";
  extraRoot.insertAdjacentHTML(
    "beforeend",
    `<div class="sociology-inline-title">Interpretaciones sin mapeo explícito</div>${renderSociologyModuleStack(leftovers)}`
  );
}

function mountNetworkConcentration() {
  const chartEl = document.getElementById("network-concentration-chart");
  if (!chartEl) return;

  const replyRows = state.reply || [];
  const inDegrees = replyRows.map((r) => Number(r.in_degree) || 0);
  const totalNodes = inDegrees.length;
  const top2Count = Math.max(1, Math.ceil(totalNodes * 0.02));
  const top2 = shareTop(inDegrees, top2Count);
  const gini = calcGini(inDegrees);
  const reciprocity = Number(state.replySummary && state.replySummary.reciprocity);
  const nodes = Number(state.replySummary && state.replySummary.nodes);
  const edges = Number(state.replySummary && state.replySummary.edges);

  setText("network-top2pct-share", fmtPercent(top2.share));
  setText("network-gini", fmtFloat(gini, 2));
  setText("network-reciprocity", fmtPercent(reciprocity));

  const cumulative = buildCumulativeCurve(inDegrees, { descending: true });
  const equality = [
    { x: 0, y: 0 },
    { x: 1, y: 1 },
  ];

  if (networkConcentrationChart) {
    networkConcentrationChart.data.datasets[0].data = cumulative;
    networkConcentrationChart.update();
  } else {
    networkConcentrationChart = new Chart(chartEl, {
      type: "line",
      data: {
        datasets: [
          {
            label: "Acumulado real (top nodos primero)",
            data: cumulative,
            parsing: false,
            borderColor: "rgba(242, 95, 44, 0.9)",
            backgroundColor: "rgba(242, 95, 44, 0.2)",
            fill: true,
            tension: 0.15,
            pointRadius: 0,
          },
          {
            label: "Distribución uniforme",
            data: equality,
            parsing: false,
            borderColor: "rgba(94, 90, 85, 0.55)",
            borderDash: [6, 6],
            pointRadius: 0,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { position: "bottom" } },
        scales: {
          x: {
            type: "linear",
            min: 0,
            max: 1,
            ticks: {
              color: "#4f4b45",
              callback: (value) => `${Math.round(Number(value) * 100)}%`,
            },
            title: { display: true, text: "% de nodos (ordenados por centralidad)" },
            grid: { color: "rgba(0,0,0,0.06)" },
          },
          y: {
            min: 0,
            max: 1,
            ticks: {
              color: "#4f4b45",
              callback: (value) => `${Math.round(Number(value) * 100)}%`,
            },
            title: { display: true, text: "% acumulado de replies recibidos" },
            grid: { color: "rgba(0,0,0,0.06)" },
          },
        },
      },
    });
  }

  setText(
    "network-concentration-note",
    `En replies, el top 2% (${fmtNumber(top2.topCount)} nodos) concentra ${fmtPercent(top2.share)} de in-degree. ` +
      `Snapshot de red: ${fmtNumber(nodes)} nodos, ${fmtNumber(edges)} aristas.`
  );
}

function mountNetworkTables() {
  const replyBody = document.querySelector("#reply-table tbody");
  const mentionBody = document.querySelector("#mention-table tbody");
  const replySearch = document.getElementById("reply-search");
  const mentionSearch = document.getElementById("mention-search");
  if (!replyBody || !mentionBody || !replySearch || !mentionSearch) return;

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

  replySearch.addEventListener("input", () => {
    const term = replySearch.value.toLowerCase();
    const filtered = state.reply
      .filter((r) => String(r.node).toLowerCase().includes(term))
      .slice(0, 50);
    replyBody.innerHTML = renderRows(filtered);
  });

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
  if (!replyBody || !mentionBody) return;

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
  if (!body || !search) return;

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
  const buttons = document.querySelectorAll(".toggle[data-metric]");
  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      buttons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const metric = btn.dataset.metric;
      mountSubmoltChart(metric);
    });
  });
}

function attachFilterToggles() {
  const langBtn = document.getElementById("language-hide-en");
  if (langBtn) {
    langBtn.addEventListener("click", () => {
      state.filters.hideLanguageEn = !state.filters.hideLanguageEn;
      langBtn.classList.toggle("active", state.filters.hideLanguageEn);
      mountLanguageChart();
      mountActiveFiltersSummary();
    });
  }

  const generalBtn = document.getElementById("submolt-hide-general");
  if (generalBtn) {
    generalBtn.addEventListener("click", () => {
      state.filters.hideSubmoltGeneral = !state.filters.hideSubmoltGeneral;
      generalBtn.classList.toggle("active", state.filters.hideSubmoltGeneral);
      const active = document.querySelector(".toggle[data-metric].active");
      const metric = (active && active.dataset && active.dataset.metric) || "posts";
      mountSubmoltChart(metric);
      mountActiveFiltersSummary();
    });
  }
}

async function loadDeferredSections() {
  try {
    const [reply, replySummary, mention, mentionSummary, replyCommunities, mentionCommunities, authors] = await Promise.all([
      loadCSV(DATA_BASE + files.reply),
      loadJSON(DATA_BASE + files.replySummary).catch(() => ({})),
      loadCSV(DATA_BASE + files.mention),
      loadJSON(DATA_BASE + files.mentionSummary).catch(() => ({})),
      loadCSV(DATA_BASE + files.replyCommunities),
      loadCSV(DATA_BASE + files.mentionCommunities),
      loadCSV(DATA_BASE + files.authors),
    ]);

    state.reply = reply;
    state.replySummary = replySummary;
    state.mention = mention;
    state.mentionSummary = mentionSummary;
    state.replyCommunities = replyCommunities;
    state.mentionCommunities = mentionCommunities;
    state.authors = authors;
    state.authorsLoaded = true;

    mountSummary();
    mountNetworkConcentration();
    mountNetworkTables();
    mountCommunityTables();
    mountAuthorTable();

    // Warm large lookup after the rest of the UI is already interactive.
    void ensureDocLookupLoaded();
  } catch (err) {
    console.error(err);
    setText("total-authors", "no disponible");
    setText("network-concentration-note", "No se pudo cargar la capa de red/autores en este momento.");
  }
}

async function init() {
  const [
    submoltStats,
    diffusionRuns,
    diffusionSubmolts,
    memeCandidates,
    memeCandidatesTechnical,
    memeCandidatesCultural,
    memeClass,
    memeBursts,
    language,
    transmission,
    coverage,
    ontologySummary,
    ontologyConcepts,
    ontologyCooccurrence,
    ontologyEmbedding2d,
    ontologySubmoltFull,
    interferenceSummary,
    embeddingsSummary,
    embeddingsPostCommentSummary,
    sociologyInterpretation,
  ] = await Promise.all([
    loadCSV(DATA_BASE + files.submoltStats),
    loadCSV(DATA_BASE + files.diffusionRuns),
    loadCSV(DATA_BASE + files.diffusionSubmolts),
    loadCSV(DATA_BASE + files.memeCandidates),
    loadCSV(DATA_BASE + files.memeCandidatesTechnical).catch(() => []),
    loadCSV(DATA_BASE + files.memeCandidatesCultural).catch(() => []),
    loadCSV(DATA_BASE + files.memeClass),
    loadCSV(DATA_BASE + files.memeBursts),
    loadCSV(DATA_BASE + files.language),
    loadCSV(DATA_BASE + files.transmission),
    loadJSON(DATA_BASE + files.coverage),
    loadCSV(DATA_BASE + files.ontologySummary),
    loadCSV(DATA_BASE + files.ontologyConcepts),
    loadCSV(DATA_BASE + files.ontologyCooccurrence),
    loadCSV(DATA_BASE + files.ontologyEmbedding2d),
    loadCSV(DATA_BASE + files.ontologySubmoltFull).catch(() => []),
    loadCSV(DATA_BASE + files.interferenceSummary).catch(() => []),
    loadJSON(DATA_BASE + files.embeddingsSummary),
    loadJSON(DATA_BASE + files.embeddingsPostCommentSummary),
    loadJSON(DATA_BASE + files.sociologyInterpretation).catch(() => null),
  ]);

  state.submolt = mergeSubmoltStats(submoltStats, diffusionSubmolts);
  state.diffusion = diffusionRuns;
  state.memeCandidates = memeCandidates;
  state.memeCandidatesTechnical = memeCandidatesTechnical;
  state.memeCandidatesCultural = memeCandidatesCultural;
  state.memeClass = memeClass;
  state.memeBursts = memeBursts;
  state.language = language;
  state.transmission = transmission;
  state.transmissionPolicy = buildTransmissionPool(transmission);
  state.transmissionVisibleCount = 0;
  state.authors = [];
  state.authorsLoaded = false;
  state.coverage = coverage;
  state.ontologySummary = ontologySummary;
  state.ontologyConcepts = ontologyConcepts;
  state.ontologyCooccurrence = ontologyCooccurrence;
  state.ontologyEmbedding2d = ontologyEmbedding2d;
  state.ontologySubmoltFull = ontologySubmoltFull;
  state.interferenceSummary = interferenceSummary;
  state.embeddingsSummary = embeddingsSummary;
  state.embeddingsPostCommentSummary = embeddingsPostCommentSummary;
  state.docLookup = {};
  state.docLookupLoaded = false;
  state.sociology = sociologyInterpretation;

  mountStrategicTLDR();
  mountSummary();
  mountCoverageQuality();
  mountCoverageConcentration();
  mountExecutiveDashboard();
  mountNarrativeLayers();
  mountEmbeddingsSummary();
  mountTransmissionTranslation();
  mountMetricContract();
  mountTraceability();
  mountLanguageChart();
  mountSubmoltChart("posts");
  mountSubmoltTable();
  attachSubmoltToggle();
  attachFilterToggles();
  mountMemeCharts();
  mountMemeLayerSplit();
  mountMemeSurvivalTable();
  mountMemeBurstTable();
  mountOntologyCharts();
  mountOntologyMap();
  mountOntologyInterpretation();
  mountOntologyCompare();
  mountOntologyTables();
  mountTransmissionTable();
  mountSociologyPanel();
  mountActiveFiltersSummary();
  mountCoherenceCheck();
  attachTextModalDelegation();
  void loadDeferredSections();
}

init().catch((err) => {
  console.error(err);
  document.body.insertAdjacentHTML(
    "beforeend",
    `<div style=\"padding:24px;color:#b00020\">No se pudieron cargar los datos. Sirve el sitio desde la raíz del repo para que ../data/derived sea accesible.</div>`
  );
});
