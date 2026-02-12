const DATA_BASE = "../data/derived/";

const files = {
  submoltStats: "submolt_stats.csv",
  diffusionRuns: "diffusion_runs.csv",
  diffusionSubmolts: "diffusion_submolts.csv",
  memeCandidates: "meme_candidates.csv",
  memeClass: "meme_classification.csv",
  reply: "reply_graph_centrality.csv",
  mention: "mention_graph_centrality.csv",
  replyCommunities: "reply_graph_communities.csv",
  mentionCommunities: "mention_graph_communities.csv",
  authors: "author_stats.csv",
  language: "public_language_distribution.csv",
  transmission: "public_transmission_samples.csv",
  embeddingsSummary: "public_embeddings_summary.json",
  embeddingsLang: "public_embeddings_lang_top.csv",
  embeddingsPairs: "public_embeddings_pairs_top.csv",
  embeddingsPostCommentSummary: "embeddings_post_comment/public_embeddings_post_comment_summary.json",
  embeddingsPostCommentLang: "embeddings_post_comment/public_embeddings_post_comment_lang_top.csv",
  embeddingsPostCommentPairs: "embeddings_post_comment/public_embeddings_post_comment_pairs_top.csv",
  coverage: "coverage_quality.json",
  ontologySummary: "ontology_summary.csv",
  ontologyConcepts: "ontology_concepts_top.csv",
  ontologyCooccurrence: "ontology_cooccurrence_top.csv",
  interferenceTop: "interference_top.csv",
  incidenceTop: "human_incidence_top.csv",
  submoltExamples: "public_submolt_examples.csv",
};

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

async function init() {
  const [
    submoltStats,
    diffusionRuns,
    diffusionSubmolts,
    memeCandidates,
    memeClass,
    reply,
    mention,
    replyCommunities,
    mentionCommunities,
    authors,
    language,
    transmission,
    embeddingsSummary,
    embeddingsLang,
    embeddingsPairs,
    embeddingsPostCommentSummary,
    embeddingsPostCommentLang,
    embeddingsPostCommentPairs,
    coverage,
    ontologySummary,
    ontologyConcepts,
    ontologyCooccurrence,
    interferenceTop,
    incidenceTop,
    submoltExamples,
  ] = await Promise.all([
    loadCSV(DATA_BASE + files.submoltStats),
    loadCSV(DATA_BASE + files.diffusionRuns),
    loadCSV(DATA_BASE + files.diffusionSubmolts),
    loadCSV(DATA_BASE + files.memeCandidates),
    loadCSV(DATA_BASE + files.memeClass),
    loadCSV(DATA_BASE + files.reply),
    loadCSV(DATA_BASE + files.mention),
    loadCSV(DATA_BASE + files.replyCommunities),
    loadCSV(DATA_BASE + files.mentionCommunities),
    loadCSV(DATA_BASE + files.authors),
    loadCSV(DATA_BASE + files.language),
    loadCSV(DATA_BASE + files.transmission),
    loadJSON(DATA_BASE + files.embeddingsSummary),
    loadCSV(DATA_BASE + files.embeddingsLang),
    loadCSV(DATA_BASE + files.embeddingsPairs),
    loadJSON(DATA_BASE + files.embeddingsPostCommentSummary),
    loadCSV(DATA_BASE + files.embeddingsPostCommentLang),
    loadCSV(DATA_BASE + files.embeddingsPostCommentPairs),
    loadJSON(DATA_BASE + files.coverage),
    loadCSV(DATA_BASE + files.ontologySummary),
    loadCSV(DATA_BASE + files.ontologyConcepts),
    loadCSV(DATA_BASE + files.ontologyCooccurrence),
    loadCSV(DATA_BASE + files.interferenceTop),
    loadCSV(DATA_BASE + files.incidenceTop),
    loadCSV(DATA_BASE + files.submoltExamples),
  ]);

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

  const topSubmolts = [...submoltStats]
    .sort((a, b) => ((b.posts || 0) + (b.comments || 0)) - ((a.posts || 0) + (a.comments || 0)))
    .slice(0, 6);
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

  const topMemeCounts = [...memeCandidates]
    .sort((a, b) => (b.count || 0) - (a.count || 0))
    .slice(0, 6);
  setTableRows(
    "report-meme-count-table",
    topMemeCounts
      .map(
        (r) => `<tr>
          <td>${r.meme}</td>
          <td>${fmtNumber(r.count)}</td>
          <td>${r.meme_type || "ngram"}</td>
        </tr>`
      )
      .join("")
  );
  const exampleMeme = topMemeCounts[0] || {};
  const exampleMemeTerm = document.getElementById("example-meme-term");
  if (exampleMemeTerm) exampleMemeTerm.textContent = exampleMeme.meme || "–";
  const exampleMemeCount = document.getElementById("example-meme-count");
  if (exampleMemeCount) exampleMemeCount.textContent = fmtNumber(exampleMeme.count);

  const topMemeLife = [...memeClass]
    .sort((a, b) => (b.lifetime_hours || 0) - (a.lifetime_hours || 0))
    .slice(0, 6);
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

  const moods = ontologySummary
    .filter((r) => r.scope === "all" && String(r.feature || "").startsWith("mood_"))
    .sort((a, b) => (b.count || 0) - (a.count || 0))
    .slice(0, 6);
  setTableRows(
    "report-moods-table",
    moods
      .map(
        (r) => `<tr>
          <td>${humanizeFeature(r.feature)}</td>
          <td>${fmtNumber(r.count)}</td>
          <td>${fmtFloat(r.rate_per_doc, 3)}</td>
        </tr>`
      )
      .join("")
  );

  const epistemic = ontologySummary
    .filter((r) => r.scope === "all" && String(r.feature || "").startsWith("epistemic_"))
    .sort((a, b) => (b.count || 0) - (a.count || 0))
    .slice(0, 6);
  setTableRows(
    "report-epistemic-table",
    epistemic
      .map(
        (r) => `<tr>
          <td>${humanizeFeature(r.feature)}</td>
          <td>${fmtNumber(r.count)}</td>
          <td>${fmtFloat(r.rate_per_doc, 3)}</td>
        </tr>`
      )
      .join("")
  );

  const concepts = ontologyConcepts.slice(0, 6);
  setTableRows(
    "report-concepts-table",
    concepts
      .map(
        (r) => `<tr>
          <td>${r.concept}</td>
          <td>${fmtNumber(r.doc_count ?? r.count)}</td>
          <td>${fmtPercent(r.share)}</td>
        </tr>`
      )
      .join("")
  );
  const exampleConcept = concepts[0] || {};
  const exampleConceptEl = document.getElementById("example-onto-concept");
  if (exampleConceptEl) exampleConceptEl.textContent = exampleConcept.concept || "–";
  const exampleConceptShare = document.getElementById("example-onto-concept-share");
  if (exampleConceptShare) exampleConceptShare.textContent = fmtPercent(exampleConcept.share);

  const cooccurrence = ontologyCooccurrence.slice(0, 6);
  setTableRows(
    "report-cooccurrence-table",
    cooccurrence
      .map(
        (r) => `<tr>
          <td>${r.concept_a}</td>
          <td>${r.concept_b}</td>
          <td>${fmtNumber(r.count)}</td>
        </tr>`
      )
      .join("")
  );
  const examplePair = cooccurrence[0] || {};
  const examplePairEl = document.getElementById("example-onto-cooccurrence");
  if (examplePairEl) {
    const a = examplePair.concept_a || "–";
    const b = examplePair.concept_b || "–";
    examplePairEl.textContent = `${a} + ${b}`;
  }
  const examplePairCount = document.getElementById("example-onto-cooccurrence-count");
  if (examplePairCount) examplePairCount.textContent = fmtNumber(examplePair.count);

  const topDiffusion = [...diffusionSubmolts]
    .sort((a, b) => (b.mean_comments || 0) - (a.mean_comments || 0))
    .slice(0, 6);
  setTableRows(
    "report-diffusion-table",
    topDiffusion
      .map(
        (r) => `<tr>
          <td>${r.submolt}</td>
          <td>${fmtFloat(r.mean_score, 2)}</td>
          <td>${fmtFloat(r.mean_comments, 2)}</td>
          <td>${fmtNumber(r.runs_seen)}</td>
        </tr>`
      )
      .join("")
  );

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

  const topMention = [...mention]
    .sort((a, b) => (b.pagerank || 0) - (a.pagerank || 0))
    .slice(0, 6);
  setTableRows(
    "report-mention-table",
    topMention
      .map(
        (r) => `<tr>
          <td>${r.node}</td>
          <td>${fmtFloat(r.pagerank, 6)}</td>
          <td>${fmtFloat(r.betweenness, 6)}</td>
        </tr>`
      )
      .join("")
  );

  const summarize = (rows) => {
    const counts = new Map();
    rows.forEach((r) => {
      const key = String(r.community);
      counts.set(key, (counts.get(key) || 0) + 1);
    });
    return [...counts.entries()]
      .map(([community, count]) => ({ community, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 6);
  };

  const replyComms = summarize(replyCommunities || []);
  setTableRows(
    "report-reply-community-table",
    replyComms
      .map(
        (r) => `<tr>
          <td>${r.community}</td>
          <td>${fmtNumber(r.count)}</td>
        </tr>`
      )
      .join("")
  );
  const exampleCommunity = replyComms[0] || {};
  const exampleCommunityId = document.getElementById("example-soc-community");
  if (exampleCommunityId) exampleCommunityId.textContent = exampleCommunity.community ?? "–";
  const exampleCommunitySize = document.getElementById("example-soc-community-size");
  if (exampleCommunitySize) exampleCommunitySize.textContent = fmtNumber(exampleCommunity.count);

  const mentionComms = summarize(mentionCommunities || []);
  setTableRows(
    "report-mention-community-table",
    mentionComms
      .map(
        (r) => `<tr>
          <td>${r.community}</td>
          <td>${fmtNumber(r.count)}</td>
        </tr>`
      )
      .join("")
  );

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
  const topLangs = Object.entries(combined)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([lang]) => lang);
  const postMap = Object.fromEntries(postsLang.map((r) => [r.lang, r.share || 0]));
  const commentMap = Object.fromEntries(commentLang.map((r) => [r.lang, r.share || 0]));
  setTableRows(
    "report-language-table",
    topLangs
      .map(
        (lang) => `<tr>
          <td>${lang}</td>
          <td>${fmtPercent(postMap[lang] || 0)}</td>
          <td>${fmtPercent(commentMap[lang] || 0)}</td>
        </tr>`
      )
      .join("")
  );

  const topTransmission = [...transmission]
    .sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")))
    .slice(0, 6);
  setTableRows(
    "report-transmission-table",
    topTransmission
      .map(
        (r) => `<tr>
          <td>${r.source}</td>
          <td>${r.submolt || "unknown"}</td>
          <td>${String(r.created_at || "").slice(0, 16).replace("T", " ")}</td>
          <td>${truncate(r.text, 120)}</td>
        </tr>`
      )
      .join("")
  );

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

  const topEmbLangs = [...embeddingsLang].slice(0, 8);
  setTableRows(
    "report-embedding-lang-table",
    topEmbLangs
      .map(
        (r) => `<tr>
          <td>${r.doc_lang}</td>
          <td>${fmtNumber(r.matches)}</td>
          <td>${fmtFloat(r.mean_score, 3)}</td>
        </tr>`
      )
      .join("")
  );

  const topEmbPairs = [...embeddingsPairs].slice(0, 6);
  setTableRows(
    "report-embedding-pairs-table",
    topEmbPairs
      .map(
        (r) => `<tr>
          <td>${fmtFloat(r.score, 3)}</td>
          <td>${r.doc_submolt || "unknown"}</td>
          <td>${r.neighbor_submolt || "unknown"}</td>
          <td>${truncate(r.doc_excerpt, 80)}</td>
          <td>${truncate(r.neighbor_excerpt, 80)}</td>
        </tr>`
      )
      .join("")
  );

  const topEmbPcLangs = [...embeddingsPostCommentLang].slice(0, 8);
  setTableRows(
    "report-embedding-pc-lang-table",
    topEmbPcLangs
      .map(
        (r) => `<tr>
          <td>${r.lang}</td>
          <td>${fmtNumber(r.matches)}</td>
          <td>${fmtFloat(r.mean_score, 3)}</td>
        </tr>`
      )
      .join("")
  );

  const topEmbPcPairs = [...embeddingsPostCommentPairs].slice(0, 6);
  setTableRows(
    "report-embedding-pc-pairs-table",
    topEmbPcPairs
      .map(
        (r) => `<tr>
          <td>${fmtFloat(r.score, 3)}</td>
          <td>${r.post_submolt || "unknown"}</td>
          <td>${r.comment_submolt || "unknown"}</td>
          <td>${truncate(r.post_excerpt, 80)}</td>
          <td>${truncate(r.comment_excerpt, 80)}</td>
        </tr>`
      )
      .join("")
  );

  const topInterference = [...interferenceTop].slice(0, 6);
  setTableRows(
    "report-interference-table",
    topInterference
      .map(
        (r) => `<tr>
          <td>${shortId(r.doc_id)}</td>
          <td>${r.doc_type}</td>
          <td>${r.submolt}</td>
          <td>${fmtFloat(r.score, 1)}</td>
          <td>${truncate(r.text_excerpt, 90)}</td>
        </tr>`
      )
      .join("")
  );
  const exampleInterference = topInterference[0] || {};
  const exampleIntDoc = document.getElementById("example-int-doc");
  if (exampleIntDoc) exampleIntDoc.textContent = exampleInterference.doc_id || "–";
  const exampleIntScore = document.getElementById("example-int-score");
  if (exampleIntScore) exampleIntScore.textContent = fmtFloat(exampleInterference.score, 1);
  const exampleIntSubmolt = document.getElementById("example-int-submolt");
  if (exampleIntSubmolt) exampleIntSubmolt.textContent = exampleInterference.submolt || "–";
  const exampleIntText = document.getElementById("example-int-text");
  if (exampleIntText) exampleIntText.textContent = truncate(exampleInterference.text_excerpt, 160) || "–";

  const topIncidence = [...incidenceTop].slice(0, 6);
  setTableRows(
    "report-incidence-table",
    topIncidence
      .map(
        (r) => `<tr>
          <td>${shortId(r.doc_id)}</td>
          <td>${r.doc_type}</td>
          <td>${r.submolt}</td>
          <td>${fmtFloat(r.human_incidence_score, 1)}</td>
          <td>${truncate(r.text_excerpt, 90)}</td>
        </tr>`
      )
      .join("")
  );
  const exampleHuman = topIncidence[0] || {};
  const exampleHumDoc = document.getElementById("example-hum-doc");
  if (exampleHumDoc) exampleHumDoc.textContent = exampleHuman.doc_id || "–";
  const exampleHumScore = document.getElementById("example-hum-score");
  if (exampleHumScore) exampleHumScore.textContent = fmtFloat(exampleHuman.human_incidence_score, 1);
  const exampleHumSubmolt = document.getElementById("example-hum-submolt");
  if (exampleHumSubmolt) exampleHumSubmolt.textContent = exampleHuman.submolt || "–";
  const exampleHumText = document.getElementById("example-hum-text");
  if (exampleHumText) exampleHumText.textContent = truncate(exampleHuman.text_excerpt, 160) || "–";

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
            <td>${truncate(r.text_excerpt, 120)}</td>
          </tr>`
        )
        .join("")
    );
  }
}

init().catch((err) => {
  console.error(err);
});
