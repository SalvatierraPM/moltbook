const Core = window.AnalyticsCore;
if (!Core) throw new Error("AnalyticsCore no esta cargado");

const DATA_BASE = Core.DATA_BASE;

const files = {
  submoltStats: "submolt_stats.csv",
  diffusionRuns: "diffusion_runs.csv",
  memeCandidates: "meme_candidates.csv",
  memeClass: "meme_classification.csv",
  reply: "reply_graph_centrality.csv",
  replyCommunities: "reply_graph_communities.csv",
  authors: "author_stats.csv",
  language: "public_language_distribution.csv",
  transmission: "public_transmission_samples.csv",
  transmissionVsmBaseline: "transmission_vsm_baseline.json",
  embeddingsSummary: "public_embeddings_summary.json",
  embeddingsPostCommentSummary: "embeddings_post_comment/public_embeddings_post_comment_summary.json",
  coverage: "coverage_quality.json",
  ontologySummary: "ontology_summary.csv",
  ontologyConcepts: "ontology_concepts_top.csv",
  ontologyCooccurrence: "ontology_cooccurrence_top.csv",
  submoltExamples: "public_submolt_examples.csv",
  docLookup: "public_doc_lookup.json",
};

const REPORT_LIMITS = {
  submoltsVolume: 25,
  memeLife: 25,
  ontologyConcepts: 25,
  ontologyCooccurrence: 25,
};

const CORE_CONCEPT_LEMMAS = Core.CORE_CONCEPT_LEMMAS;
const TRANSMISSION_TEXT_MIN_CHARS = Core.TRANSMISSION_TEXT_MIN_CHARS;
const METRIC_CONTRACT_ROWS = Core.METRIC_CONTRACT_ROWS;
const loadCSV = Core.loadCSV;
const loadJSON = Core.loadJSON;
const parseDate = Core.parseDate;
const conceptLemma = Core.conceptLemma;
const isVariantPair = Core.isVariantPair;
const buildTransmissionPool = Core.buildTransmissionPool;

function escapeHtml(text) {
  return String(text || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;")
    .replaceAll("'", "&#039;");
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

function fmtDate(dt) {
  if (!dt) return "–";
  return dt.toISOString().slice(0, 16).replace("T", " ") + " UTC";
}

function truncate(text, max = 120) {
  if (!text) return "";
  const clean = String(text).replace(/\s+/g, " ").trim();
  if (clean.length <= max) return clean;
  return `${clean.slice(0, max - 1)}…`;
}

function shortId(value) {
  if (!value) return "–";
  return String(value).slice(0, 8);
}

function setTableRows(id, rowsHtml) {
  const tbody = document.querySelector(`#${id} tbody`);
  if (!tbody) return;
  tbody.innerHTML = rowsHtml;
}

function setText(id, value) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = value;
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

function mountMetricContractTable() {
  setTableRows(
    "report-metric-contract-table",
    METRIC_CONTRACT_ROWS.map(
      ([module, metric, source, transform, axis]) => `<tr>
        <td>${escapeHtml(module)}</td>
        <td>${escapeHtml(metric)}</td>
        <td>${escapeHtml(source)}</td>
        <td>${escapeHtml(transform)}</td>
        <td>${escapeHtml(axis)}</td>
      </tr>`
    ).join("")
  );
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

async function init() {
  const [
    submoltStats,
    diffusionRuns,
    memeCandidates,
    memeClass,
    reply,
    replyCommunities,
    authors,
    language,
    transmission,
    transmissionVsmBaseline,
    embeddingsSummary,
    embeddingsPostCommentSummary,
    coverage,
    ontologySummary,
    ontologyConcepts,
    ontologyCooccurrence,
    submoltExamples,
  ] = await Promise.all([
    loadCSV(DATA_BASE + files.submoltStats),
    loadCSV(DATA_BASE + files.diffusionRuns),
    loadCSV(DATA_BASE + files.memeCandidates),
    loadCSV(DATA_BASE + files.memeClass),
    loadCSV(DATA_BASE + files.reply),
    loadCSV(DATA_BASE + files.replyCommunities),
    loadCSV(DATA_BASE + files.authors),
    loadCSV(DATA_BASE + files.language),
    loadCSV(DATA_BASE + files.transmission),
    loadJSON(DATA_BASE + files.transmissionVsmBaseline),
    loadJSON(DATA_BASE + files.embeddingsSummary),
    loadJSON(DATA_BASE + files.embeddingsPostCommentSummary),
    loadJSON(DATA_BASE + files.coverage),
    loadCSV(DATA_BASE + files.ontologySummary),
    loadCSV(DATA_BASE + files.ontologyConcepts),
    loadCSV(DATA_BASE + files.ontologyCooccurrence),
    loadCSV(DATA_BASE + files.submoltExamples),
  ]);

  const filters = {
    hideGeneral: false,
    hideEn: false,
  };
  const txPolicy = buildTransmissionPool(transmission);
  let visibleTransmissionRows = 0;

  let docLookupMap = null;
  let docLookupLoaded = false;
  let docLookupPromise = null;
  const ensureDocLookupLoaded = async () => {
    if (docLookupLoaded) return docLookupMap || {};
    if (!docLookupPromise) {
      docLookupPromise = loadJSON(DATA_BASE + files.docLookup)
        .then((payload) => {
          docLookupMap = (payload && payload.docs) || {};
          return docLookupMap;
        })
        .catch(() => {
          docLookupMap = {};
          return docLookupMap;
        })
        .finally(() => {
          docLookupLoaded = true;
          docLookupPromise = null;
        });
    }
    return docLookupPromise;
  };

  const lookupDocText = (docId) => {
    if (!docId || !docLookupMap) return null;
    const hit = docLookupMap[String(docId)];
    if (hit && typeof hit.text === "string") return hit.text;
    return null;
  };

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
    const meta = [
      docType && `tipo=${docType}`,
      submolt && `submolt=${submolt}`,
      createdAt && `fecha=${createdAt}`,
      score && `score=${score}`,
    ]
      .filter(Boolean)
      .join(" · ");
    openTextModal({ title: `Doc ${shortId(docId)}`, meta, text });
  });

  const totalPosts = submoltStats.reduce((acc, r) => acc + (r.posts || 0), 0);
  const totalComments = submoltStats.reduce((acc, r) => acc + (r.comments || 0), 0);
  const totalSubmolts = submoltStats.length;
  const totalRuns = new Set(diffusionRuns.map((r) => r.run_id)).size;
  const totalAuthors = authors.length;

  const runDates = diffusionRuns.map((r) => parseDate(r.run_time)).filter(Boolean);
  const captureMax = runDates.length ? new Date(Math.max(...runDates)) : null;
  const createdMins = [coverage.posts_created_min, coverage.comments_created_min]
    .map(parseDate)
    .filter(Boolean);
  const createdMaxs = [coverage.posts_created_max, coverage.comments_created_max]
    .map(parseDate)
    .filter(Boolean);
  const createdMin = createdMins.length ? new Date(Math.min(...createdMins)) : null;
  const createdMax = createdMaxs.length ? new Date(Math.max(...createdMaxs)) : null;

  const sumLanguageShare = (scope) => Core.sumLanguageShare(language, scope);
  const sumLanguageCount = (scope) => Core.sumLanguageCount(language, scope);

  const renderActiveFiltersSection = () => {
    const variantPairs = ontologyCooccurrence.filter((r) => isVariantPair(r.concept_a, r.concept_b)).length;
    const rows = [
      [
        "Ontologia",
        "Excluir pares variantes (lemma equivalente)",
        "activo",
        `${fmtNumber(variantPairs)} pares variantes excluidos del ranking`,
      ],
      [
        "Transmision",
        `Texto >= ${TRANSMISSION_TEXT_MIN_CHARS} chars + prioridad co-mencion humano+IA`,
        "activo",
        `Pool=${fmtNumber(txPolicy.pool.length)} de ${fmtNumber(txPolicy.totals.raw)} (${txPolicy.policy}); vista=${fmtNumber(visibleTransmissionRows)}`,
      ],
      [
        "Idiomas",
        "Ocultar ingles (en)",
        filters.hideEn ? "activo" : "inactivo",
        filters.hideEn ? "La tabla excluye 'en'" : "Se muestran todos los idiomas",
      ],
      [
        "Submolts",
        "Ocultar general",
        filters.hideGeneral ? "activo" : "inactivo",
        filters.hideGeneral ? "La tabla de volumen excluye 'general'" : "Sin exclusiones de submolt",
      ],
    ];
    setTableRows(
      "report-active-filters-table",
      rows
        .map(
          ([module, filter, status, impact]) => `<tr>
            <td>${escapeHtml(module)}</td>
            <td>${escapeHtml(filter)}</td>
            <td>${escapeHtml(status)}</td>
            <td>${escapeHtml(impact)}</td>
          </tr>`
        )
        .join("")
    );
  };

  const renderTraceabilitySection = () => {
    const runMin = runDates.length ? new Date(Math.min(...runDates)) : null;
    const runMax = runDates.length ? new Date(Math.max(...runDates)) : null;
    const rows = [
      ["Rango created_at", `${fmtDate(createdMin)} — ${fmtDate(createdMax)}`],
      ["Rango run_time", `${fmtDate(runMin)} — ${fmtDate(runMax)}`],
      ["Runs unicos", fmtNumber(totalRuns)],
      ["Volumen snapshot", `${fmtNumber(totalPosts)} posts / ${fmtNumber(totalComments)} comentarios`],
      [
        "Muestra idioma",
        `${fmtNumber(sumLanguageCount("posts"))} posts + ${fmtNumber(sumLanguageCount("comments"))} comentarios`,
      ],
      ["Muestra transmision", `${fmtNumber(txPolicy.pool.length)} docs (de ${fmtNumber(txPolicy.totals.raw)} raw)`],
      ["Politica transmision activa", txPolicy.policy],
      ["Version criterios", "v1.1 (co-ocurrencia sin variantes + transmision canonica)"],
    ];
    setTableRows(
      "report-traceability-table",
      rows
        .map(
          ([item, value]) => `<tr>
            <td>${escapeHtml(item)}</td>
            <td>${escapeHtml(value)}</td>
          </tr>`
        )
        .join("")
    );
  };

  const renderCoherenceSection = () => {
    const filteredPairs = ontologyCooccurrence
      .filter((r) => !isVariantPair(r.concept_a, r.concept_b))
      .slice(0, REPORT_LIMITS.ontologyCooccurrence);
    const hasVariantInTop = filteredPairs.some((r) => isVariantPair(r.concept_a, r.concept_b));

    const rebuiltTx = buildTransmissionPool(transmission);
    const txPolicyMatch = txPolicy.pool.length === rebuiltTx.pool.length && txPolicy.policy === rebuiltTx.policy;

    const postShare = sumLanguageShare("posts");
    const commentShare = sumLanguageShare("comments");
    const languageShareOk = Math.abs(postShare - 1) <= 0.03 && Math.abs(commentShare - 1) <= 0.03;

    const postsMin = parseDate(coverage.posts_created_min);
    const postsMax = parseDate(coverage.posts_created_max);
    const commentsMin = parseDate(coverage.comments_created_min);
    const commentsMax = parseDate(coverage.comments_created_max);
    const postsRangeOk = Boolean(postsMin && postsMax && postsMin <= postsMax);
    const commentsRangeOk = Boolean(commentsMin && commentsMax && commentsMin <= commentsMax);
    const rangesOk = postsRangeOk && commentsRangeOk;

    const totalsOk = totalPosts > 0 && totalComments > 0;
    const checks = [
      [
        "Co-ocurrencia top sin pares variantes",
        !hasVariantInTop,
        `${fmtNumber(filteredPairs.length)} filas; variantes en top=${hasVariantInTop ? "si" : "no"}`,
      ],
      ["Pool de transmision canonico", txPolicyMatch, `${fmtNumber(txPolicy.pool.length)} filas; policy=${txPolicy.policy}`],
      ["Shares de idioma normalizados", languageShareOk, `posts=${postShare.toFixed(3)} / comments=${commentShare.toFixed(3)}`],
      ["Rangos temporales validos", rangesOk, `posts=${postsRangeOk ? "ok" : "fail"}, comments=${commentsRangeOk ? "ok" : "fail"}`],
      ["Volumen base no vacio", totalsOk, `${fmtNumber(totalSubmolts)} submolts activos`],
    ];
    setTableRows(
      "report-coherence-table",
      checks
        .map(
          ([name, ok, detail]) => `<tr>
            <td>${escapeHtml(name)}</td>
            <td>${ok ? "PASS" : "FAIL"}</td>
            <td>${escapeHtml(detail)}</td>
          </tr>`
        )
        .join("")
    );
  };

  document.getElementById("stat-posts").textContent = fmtNumber(totalPosts);
  document.getElementById("stat-comments").textContent = fmtNumber(totalComments);
  document.getElementById("stat-submolts").textContent = fmtNumber(totalSubmolts);
  document.getElementById("stat-authors").textContent = fmtNumber(totalAuthors);
  document.getElementById("stat-runs").textContent = fmtNumber(totalRuns);
  document.getElementById("stat-range").textContent = `${fmtDate(createdMin)} — ${fmtDate(createdMax)}`;
  document.getElementById("stat-updated").textContent = fmtDate(captureMax || createdMax);

  document.getElementById("coverage-posts-range").textContent =
    `${fmtDate(parseDate(coverage.posts_created_min))} — ${fmtDate(parseDate(coverage.posts_created_max))}`;
  document.getElementById("coverage-comments-range").textContent =
    `${fmtDate(parseDate(coverage.comments_created_min))} — ${fmtDate(parseDate(coverage.comments_created_max))}`;
  document.getElementById("coverage-ratio").textContent = fmtFloat(coverage.post_comment_ratio, 2);
  document.getElementById("coverage-dup-posts").textContent = fmtNumber(coverage.posts_duplicates);
  document.getElementById("coverage-dup-comments").textContent = fmtNumber(coverage.comments_duplicates);

  const aboutPosts = document.getElementById("about-posts");
  if (aboutPosts) aboutPosts.textContent = fmtNumber(totalPosts);
  const aboutComments = document.getElementById("about-comments");
  if (aboutComments) aboutComments.textContent = fmtNumber(totalComments);
  const aboutWindow = document.getElementById("about-window");
  if (aboutWindow) aboutWindow.textContent = `${fmtDate(createdMin)} — ${fmtDate(createdMax)}`;

  mountMetricContractTable();
  renderTraceabilitySection();
  renderCoherenceSection();
  renderActiveFiltersSection();

  const renderSubmoltVolumeTable = () => {
    const topSubmolts = [...submoltStats]
      .filter((r) => (filters.hideGeneral ? String(r.submolt || "").toLowerCase() !== "general" : true))
      .sort((a, b) => ((b.posts || 0) + (b.comments || 0)) - ((a.posts || 0) + (a.comments || 0)))
      .slice(0, REPORT_LIMITS.submoltsVolume);
    setTableRows(
      "report-submolt-table",
      topSubmolts
        .map(
          (r) => `<tr>
            <td>${r.submolt}</td>
            <td>${fmtNumber(r.posts)}</td>
            <td>${fmtNumber(r.comments)}</td>
            <td>${fmtFloat(r.mean_upvotes, 1)}</td>
          </tr>`
        )
        .join("")
    );
  };
  renderSubmoltVolumeTable();
  const hideGeneralBtn = document.getElementById("report-submolts-hide-general");
  if (hideGeneralBtn) {
    hideGeneralBtn.addEventListener("click", () => {
      filters.hideGeneral = !filters.hideGeneral;
      hideGeneralBtn.classList.toggle("active", filters.hideGeneral);
      renderSubmoltVolumeTable();
      renderActiveFiltersSection();
    });
  }

  const topMemeCounts = [...memeCandidates]
    .sort((a, b) => (b.count || 0) - (a.count || 0))
    .slice(0, 6);
  const exampleMeme = topMemeCounts[0] || {};
  const exampleMemeTerm = document.getElementById("example-meme-term");
  if (exampleMemeTerm) exampleMemeTerm.textContent = exampleMeme.meme || "–";
  const exampleMemeCount = document.getElementById("example-meme-count");
  if (exampleMemeCount) exampleMemeCount.textContent = fmtNumber(exampleMeme.count);

  const topMemeLife = [...memeClass]
    .sort((a, b) => (b.lifetime_hours || 0) - (a.lifetime_hours || 0))
    .slice(0, REPORT_LIMITS.memeLife);
  setTableRows(
    "report-meme-life-table",
    topMemeLife
      .map(
        (r) => `<tr>
          <td>${r.meme}</td>
          <td>${fmtFloat(r.lifetime_hours, 1)}</td>
          <td>${fmtNumber(r.submolts_touched)}</td>
          <td>${r.class || "–"}</td>
        </tr>`
      )
      .join("")
  );
  const exampleLife = topMemeLife[0] || {};
  const exampleLifeTerm = document.getElementById("example-meme-life-term");
  if (exampleLifeTerm) exampleLifeTerm.textContent = exampleLife.meme || "–";
  const exampleLifeHours = document.getElementById("example-meme-life-hours");
  if (exampleLifeHours) exampleLifeHours.textContent = fmtFloat(exampleLife.lifetime_hours, 1);
  const exampleLifeClass = document.getElementById("example-meme-life-class");
  if (exampleLifeClass) exampleLifeClass.textContent = exampleLife.class || "–";
  const exampleLifeSubmolts = document.getElementById("example-meme-life-submolts");
  if (exampleLifeSubmolts) exampleLifeSubmolts.textContent = fmtNumber(exampleLife.submolts_touched);

  const acts = ontologySummary
    .filter((r) => r.scope === "all" && String(r.feature || "").startsWith("act_"))
    .sort((a, b) => (b.count || 0) - (a.count || 0))
    .slice(0, 6);
  setTableRows(
    "report-acts-table",
    acts
      .map(
        (r) => `<tr>
          <td>${humanizeFeature(r.feature)}</td>
          <td>${fmtNumber(r.count)}</td>
          <td>${fmtFloat(r.rate_per_doc, 3)}</td>
        </tr>`
      )
      .join("")
  );
  const exampleAct = acts[0] || {};
  const exampleActEl = document.getElementById("example-onto-act");
  if (exampleActEl) exampleActEl.textContent = exampleAct.feature ? humanizeFeature(exampleAct.feature) : "–";
  const exampleActRate = document.getElementById("example-onto-act-rate");
  if (exampleActRate) exampleActRate.textContent = fmtFloat(exampleAct.rate_per_doc, 3);

  const concepts = ontologyConcepts.slice(0, REPORT_LIMITS.ontologyConcepts);
  const exampleCoreConcept = concepts[0] || {};
  const exampleCoreConceptEl = document.getElementById("example-onto-core-concept");
  if (exampleCoreConceptEl) exampleCoreConceptEl.textContent = exampleCoreConcept.concept || "–";
  const exampleCoreConceptShare = document.getElementById("example-onto-core-concept-share");
  if (exampleCoreConceptShare) exampleCoreConceptShare.textContent = fmtPercent(exampleCoreConcept.share);

  const noCoreConcepts = [...ontologyConcepts].filter((r) => !CORE_CONCEPT_LEMMAS.has(conceptLemma(r.concept)));
  const exampleNoCoreConcept = noCoreConcepts[0] || {};
  const exampleNoCoreConceptEl = document.getElementById("example-onto-concept-nocore");
  if (exampleNoCoreConceptEl) exampleNoCoreConceptEl.textContent = exampleNoCoreConcept.concept || "–";
  const exampleNoCoreConceptShare = document.getElementById("example-onto-concept-nocore-share");
  if (exampleNoCoreConceptShare) exampleNoCoreConceptShare.textContent = fmtPercent(exampleNoCoreConcept.share);

  const noCorePairs = [...ontologyCooccurrence]
    .filter((r) => !isVariantPair(r.concept_a, r.concept_b))
    .filter((r) => !CORE_CONCEPT_LEMMAS.has(conceptLemma(r.concept_a)) && !CORE_CONCEPT_LEMMAS.has(conceptLemma(r.concept_b)));
  const examplePairNoCore = noCorePairs[0] || {};
  const examplePairNoCoreEl = document.getElementById("example-onto-cooccurrence-nocore");
  if (examplePairNoCoreEl) {
    const a = examplePairNoCore.concept_a || "–";
    const b = examplePairNoCore.concept_b || "–";
    examplePairNoCoreEl.textContent = `${a} + ${b}`;
  }
  const examplePairNoCoreCount = document.getElementById("example-onto-cooccurrence-nocore-count");
  if (examplePairNoCoreCount) examplePairNoCoreCount.textContent = fmtNumber(examplePairNoCore.count);

  const totalDocs = (() => {
    const first = ontologyConcepts && ontologyConcepts.length ? ontologyConcepts[0] : null;
    const docCount = first && first.doc_count ? Number(first.doc_count) : null;
    const share = first && first.share ? Number(first.share) : null;
    if (docCount && share) return docCount / share;
    return null;
  })();

  const insightConceptEl = document.getElementById("insight-onto-concepts-nocore");
  const insightPairEl = document.getElementById("insight-onto-pairs-nocore");

  const renderRankRows = (rows, max, valueText, labelText) =>
    rows
      .map((r) => {
        const label = labelText(r);
        const value = Number(r.value) || 0;
        const pct = max > 0 ? (value / max) * 100 : 0;
        return `<div class="rank-row">
          <div class="rank-label" title="${escapeHtml(label)}">${escapeHtml(label)}</div>
          <div class="rank-bar"><span style="width:${pct.toFixed(1)}%"></span></div>
          <div class="rank-value">${valueText(r)}</div>
        </div>`;
      })
      .join("");

  if (insightConceptEl) {
    const topNoCore = noCoreConcepts.slice(0, 8);
    const maxShare = topNoCore.length ? Number(topNoCore[0].share) || 0 : 0;
    const rows = topNoCore.map((r) => ({ raw: r, value: r.share }));
    insightConceptEl.innerHTML = rows.length
      ? renderRankRows(rows, maxShare, (x) => fmtPercent(x.raw.share), (x) => x.raw.concept)
      : "–";
  }

  if (insightPairEl) {
    const topNoCorePairs = noCorePairs.slice(0, 8);
    const maxCount = topNoCorePairs.length ? Number(topNoCorePairs[0].count) || 0 : 0;
    const rows = topNoCorePairs.map((r) => ({ raw: r, value: r.count }));
    insightPairEl.innerHTML = rows.length
      ? renderRankRows(
          rows,
          maxCount,
          (x) => {
            const share = totalDocs ? ` (${fmtPercent(Number(x.raw.count) / totalDocs)})` : "";
            return `${fmtNumber(x.raw.count)}${share}`;
          },
          (x) => `${x.raw.concept_a} + ${x.raw.concept_b}`
        )
      : "–";
  }

  const vsm = transmissionVsmBaseline || {};
  const metricsAll = (vsm.metrics && (vsm.metrics._all || vsm.metrics.all)) || {};
  const corrEl = document.getElementById("vsm-corr");
  if (corrEl) corrEl.textContent = fmtFloat(metricsAll.corr_embedding_vs_vsm, 2);
  const aucEl = document.getElementById("vsm-auc");
  if (aucEl) aucEl.textContent = fmtFloat(metricsAll.auc_vsm_matched_vs_shuffled, 3);
  const meanMatchedEl = document.getElementById("vsm-mean-matched");
  if (meanMatchedEl) meanMatchedEl.textContent = fmtFloat(metricsAll.vsm_matched?.mean, 3);
  const meanRandomEl = document.getElementById("vsm-mean-random");
  if (meanRandomEl) meanRandomEl.textContent = fmtFloat(metricsAll.vsm_shuffled?.mean, 3);

  const topReply = [...reply]
    .sort((a, b) => (b.pagerank || 0) - (a.pagerank || 0))
    .slice(0, 6);
  setTableRows(
    "report-reply-table",
    topReply
      .map(
        (r) => `<tr>
          <td>${r.node}</td>
          <td>${fmtFloat(r.pagerank, 6)}</td>
          <td>${fmtFloat(r.betweenness, 6)}</td>
        </tr>`
      )
      .join("")
  );
  const exampleReply = topReply[0] || {};
  const exampleReplyNode = document.getElementById("example-soc-reply-node");
  if (exampleReplyNode) exampleReplyNode.textContent = exampleReply.node || "–";
  const exampleReplyPr = document.getElementById("example-soc-reply-pr");
  if (exampleReplyPr) exampleReplyPr.textContent = fmtFloat(exampleReply.pagerank, 6);

  const summarize = (rows) => {
    const total = rows.length || 1;
    const counts = new Map();
    rows.forEach((r) => {
      const key = String(r.community);
      counts.set(key, (counts.get(key) || 0) + 1);
    });
    return [...counts.entries()]
      .map(([community, count]) => ({ community, count, share: count / total }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 6);
  };

  const replyComms = summarize(replyCommunities || []);
  const exampleCommunity = replyComms[0] || {};
  const exampleCommunityId = document.getElementById("example-soc-community");
  if (exampleCommunityId) exampleCommunityId.textContent = exampleCommunity.community ?? "–";
  const exampleCommunitySize = document.getElementById("example-soc-community-size");
  if (exampleCommunitySize) exampleCommunitySize.textContent = fmtNumber(exampleCommunity.count);

  const topAuthors = [...authors]
    .map((r) => ({
      ...r,
      total: (r.posts || 0) + (r.comments || 0),
      submolts_total: (r.post_submolts || 0) + (r.comment_submolts || 0),
    }))
    .sort((a, b) => b.total - a.total)
    .slice(0, 6);
  setTableRows(
    "report-author-table",
    topAuthors
      .map(
        (r) => `<tr>
          <td>${r.author_id}</td>
          <td>${fmtNumber(r.posts)}</td>
          <td>${fmtNumber(r.comments)}</td>
          <td>${fmtNumber(r.submolts_total)}</td>
        </tr>`
      )
      .join("")
  );
  const exampleAuthor = topAuthors[0] || {};
  const exampleAuthorEl = document.getElementById("example-soc-author");
  if (exampleAuthorEl) exampleAuthorEl.textContent = exampleAuthor.author_id || "–";
  const exampleAuthorTotal = document.getElementById("example-soc-author-total");
  if (exampleAuthorTotal) exampleAuthorTotal.textContent = fmtNumber(exampleAuthor.total);

  const postsLang = language.filter((r) => r.scope === "posts");
  const commentLang = language.filter((r) => r.scope === "comments");
  const combined = {};
  postsLang.forEach((r) => {
    combined[r.lang] = (combined[r.lang] || 0) + (r.share || 0);
  });
  commentLang.forEach((r) => {
    combined[r.lang] = (combined[r.lang] || 0) + (r.share || 0);
  });
  const postMap = Object.fromEntries(postsLang.map((r) => [r.lang, r.share || 0]));
  const commentMap = Object.fromEntries(commentLang.map((r) => [r.lang, r.share || 0]));

  const renderLanguageTable = () => {
    const top = Object.entries(combined)
      .sort((a, b) => b[1] - a[1])
      .filter(([lang]) => (filters.hideEn ? lang !== "en" : true))
      .slice(0, 6)
      .map(([lang]) => lang);
    setTableRows(
      "report-language-table",
      top
        .map(
          (lang) => `<tr>
            <td>${lang}</td>
            <td>${fmtPercent(postMap[lang] || 0)}</td>
            <td>${fmtPercent(commentMap[lang] || 0)}</td>
          </tr>`
        )
        .join("")
    );
  };

  renderLanguageTable();
  const hideEnBtn = document.getElementById("report-language-hide-en");
  if (hideEnBtn) {
    hideEnBtn.addEventListener("click", () => {
      filters.hideEn = !filters.hideEn;
      hideEnBtn.classList.toggle("active", filters.hideEn);
      renderLanguageTable();
      renderActiveFiltersSection();
    });
  }

  const topTransmission = [...txPolicy.pool].slice(0, 6);
  visibleTransmissionRows = topTransmission.length;
  setTableRows(
    "report-transmission-table",
    topTransmission
      .map(
        (r) => `<tr>
          <td>${r.source}</td>
          <td>${r.submolt || "unknown"}</td>
          <td>${String(r.created_at || "").slice(0, 16).replace("T", " ")}</td>
          <td class="cell-text">${escapeHtml(r.text)}</td>
        </tr>`
      )
      .join("")
  );
  renderActiveFiltersSection();

  if (embeddingsSummary) {
    const embDocs = document.getElementById("emb-docs");
    if (embDocs) embDocs.textContent = fmtNumber(embeddingsSummary.total_docs);
    const embMatches = document.getElementById("emb-matches");
    if (embMatches) embMatches.textContent = fmtNumber(embeddingsSummary.total_matches);
    const embMean = document.getElementById("emb-mean");
    if (embMean) embMean.textContent = fmtFloat(embeddingsSummary.mean_score, 3);
    const embCross = document.getElementById("emb-cross");
    if (embCross) embCross.textContent = fmtPercent(embeddingsSummary.cross_submolt_rate);
    const embLangs = document.getElementById("emb-langs");
    if (embLangs) embLangs.textContent = fmtNumber(embeddingsSummary.langs_indexed);
  }

  if (embeddingsPostCommentSummary) {
    const embPcPosts = document.getElementById("embpc-posts");
    if (embPcPosts) embPcPosts.textContent = fmtNumber(embeddingsPostCommentSummary.total_posts);
    const embPcComments = document.getElementById("embpc-comments");
    if (embPcComments) embPcComments.textContent = fmtNumber(embeddingsPostCommentSummary.total_comments);
    const embPcMatches = document.getElementById("embpc-matches");
    if (embPcMatches) embPcMatches.textContent = fmtNumber(embeddingsPostCommentSummary.total_matches);
    const embPcMean = document.getElementById("embpc-mean");
    if (embPcMean) embPcMean.textContent = fmtFloat(embeddingsPostCommentSummary.mean_score, 3);
    const embPcCross = document.getElementById("embpc-cross");
    if (embPcCross) embPcCross.textContent = fmtPercent(embeddingsPostCommentSummary.cross_submolt_rate);
  }

  const submoltVolumes = submoltStats
    .map((r) => (Number(r.posts) || 0) + (Number(r.comments) || 0))
    .sort((a, b) => b - a);
  const totalVolume = submoltVolumes.reduce((acc, v) => acc + v, 0);
  const top5Volume = submoltVolumes.slice(0, 5).reduce((acc, v) => acc + v, 0);
  const top5Share = totalVolume > 0 ? top5Volume / totalVolume : null;

  const topActRow = acts[0] || null;
  const totalActCount = acts.reduce((acc, r) => acc + (Number(r.count) || 0), 0);
  const topActShare = topActRow && totalActCount > 0 ? (Number(topActRow.count) || 0) / totalActCount : null;

  const topMeme = topMemeLife[0] || null;
  const topNetworkNode = topReply[0] || null;
  const crossRate = embeddingsPostCommentSummary ? Number(embeddingsPostCommentSummary.cross_submolt_rate) : null;
  const crossMean = embeddingsPostCommentSummary ? Number(embeddingsPostCommentSummary.mean_score) : null;
  const duplicateRateComments =
    totalComments > 0 ? (Number(coverage.comments_duplicates) || 0) / totalComments : null;

  setText("obs-finding-concentration-signal", `Top 5 submolts concentran ${fmtPercent(top5Share)} del volumen.`);
  setText(
    "obs-finding-memetics-signal",
    topMeme
      ? `"${topMeme.meme}" dura ${fmtFloat(topMeme.lifetime_hours, 1)} hrs y toca ${fmtNumber(topMeme.submolts_touched)} submolts.`
      : "Sin datos suficientes de vida memetica."
  );
  setText(
    "obs-finding-ontology-signal",
    topActRow
      ? `Predomina ${humanizeFeature(topActRow.feature)} con share ${fmtPercent(topActShare)} en actos top.`
      : "Sin datos ontologicos suficientes."
  );
  setText(
    "obs-finding-network-signal",
    topNetworkNode
      ? `Nodo top ${String(topNetworkNode.node)} (PageRank ${fmtFloat(topNetworkNode.pagerank, 6)}).`
      : "Sin datos de red para este snapshot."
  );
  setText(
    "obs-finding-transmission-signal",
    `Cross-submolt post→comentario ${fmtPercent(crossRate)} (similitud media ${fmtFloat(crossMean, 3)}).`
  );
  setText(
    "obs-finding-quality-signal",
    `Duplicados: posts ${fmtNumber(coverage.posts_duplicates)} / comentarios ${fmtNumber(coverage.comments_duplicates)} (${fmtPercent(
      duplicateRateComments
    )}).`
  );

  if (submoltExamples && submoltExamples.length) {
    const rows = [...submoltExamples];
    setTableRows(
      "report-submolt-examples-table",
      rows
        .map(
          (r) => `<tr>
            <td>${r.submolt}</td>
            <td>${r.doc_type}</td>
            <td>${String(r.created_at || "").slice(0, 16).replace("T", " ")}</td>
            <td>${shortId(r.doc_id)}</td>
            <td>${fmtNumber(r.upvotes)}</td>
            <td class="cell-text">
              <button
                class="text-link"
                type="button"
                data-doc-id="${escapeHtml(r.doc_id)}"
                data-doc-type="${escapeHtml(r.doc_type)}"
                data-doc-submolt="${escapeHtml(r.submolt)}"
                data-doc-created-at="${escapeHtml(String(r.created_at || "").slice(0, 16).replace("T", " "))}"
              >${escapeHtml(truncate(r.text_excerpt, 200))}</button>
            </td>
          </tr>`
        )
        .join("")
    );
  }

  // Load the text lookup in background after first paint.
  void ensureDocLookupLoaded();
}

init().catch((err) => {
  console.error(err);
  document.body.insertAdjacentHTML(
    "beforeend",
    `<div style=\"padding:24px;color:#b00020\">No se pudieron cargar los datos. Sirve el sitio desde la raiz del repo para que ../data/derived sea accesible.</div>`
  );
});
