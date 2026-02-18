(function bootstrapAnalyticsCore(global) {
  const DATA_BASE = "../data/derived/";

  const TRANSMISSION_TEXT_MIN_CHARS = 40;
  const TRANSMISSION_HUMAN_RE = /\b(human|humano)\b/i;
  const TRANSMISSION_AI_RE = /\b(ai|agent|agents)\b/i;

  const CORE_CONCEPT_LEMMAS = new Set(["agent", "human", "ai"]);
  const CONCEPT_LEMMA_MAP = {
    agents: "agent",
    humans: "human",
    tokens: "token",
    models: "model",
    tools: "tool",
    prompts: "prompt",
    policies: "policy",
    memes: "meme",
    modelo: "model",
    lenguaje: "language",
    ontologia: "ontology",
    etica: "ethics",
  };

  const METRIC_CONTRACT_ROWS = [
    ["Cobertura", "Volumen total", "submolt_stats.csv + author_stats.csv", "Suma por submolt + conteo únicos", "created_at"],
    ["Memética", "Vida y burst", "meme_classification.csv + meme_bursts.csv", "Top por vida y burst score", "created_at"],
    ["Ontología", "Co-ocurrencia", "ontology_cooccurrence_top.csv", "Excluir pares variantes (lemma equivalente)", "created_at"],
    ["Redes", "Centralidad", "reply/mention_graph_*.csv", "Top por PageRank y betweenness", "created_at"],
    ["Idiomas", "Distribución", "public_language_distribution.csv", "Muestra estadística por scope", "created_at (muestra)"],
    ["Transmisión", "Muestras narrativas", "public_transmission_samples.csv", `Texto >= ${TRANSMISSION_TEXT_MIN_CHARS} chars; priorizar co-mención humano+IA`, "created_at"],
  ];

  const CONFIDENCE_ROWS = [
    ["Cobertura", "alta", "Conteos directos y trazables sobre derivados estables."],
    ["Difusión", "media", "Depende del eje temporal elegido y del muestreo por run."],
    ["Memética", "media", "N-gramas y bursts son descriptivos; requieren contexto cualitativo."],
    ["Ontología", "media", "Heurísticas interpretables, con límites en ironía/sinonimia."],
    ["Interferencia", "media", "Score útil para triage, no prueba causal de intención."],
    ["Redes", "media", "Centralidad estructural robusta, pero no equivale a autoridad real."],
    ["Idiomas", "media", "Estimación por muestra, no censo completo."],
    ["Transmisión", "media-baja", "Muestra curada para lectura narrativa; no representa todo el corpus."],
  ];

  function coerceValue(value) {
    if (value === undefined || value === null) return null;
    const raw = String(value).trim();
    if (!raw) return null;
    if (/^-?\d+(\.\d+)?$/.test(raw)) return Number(raw);
    return raw;
  }

  function parseCSVText(text) {
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

  function loadCSV(path) {
    if (global.Papa && global.Papa.parse) {
      return new Promise((resolve, reject) => {
        global.Papa.parse(path, {
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
      .then(parseCSVText);
  }

  async function loadJSON(path) {
    const res = await fetch(path);
    if (!res.ok) throw new Error(`No se pudo cargar ${path}`);
    return res.json();
  }

  function conceptLemma(concept) {
    const raw = String(concept || "").trim().toLowerCase();
    return CONCEPT_LEMMA_MAP[raw] || raw;
  }

  function isVariantPair(a, b) {
    return conceptLemma(a) === conceptLemma(b);
  }

  function buildTransmissionPool(rows) {
    const all = Array.isArray(rows) ? rows : [];
    const nonTrivial = all.filter((r) => String(r.text || "").trim().length >= TRANSMISSION_TEXT_MIN_CHARS);
    const coMention = nonTrivial.filter((r) => {
      const text = String(r.text || "");
      return TRANSMISSION_HUMAN_RE.test(text) && TRANSMISSION_AI_RE.test(text);
    });
    const aiOnly = nonTrivial.filter((r) => TRANSMISSION_AI_RE.test(String(r.text || "")));
    const pool = coMention.length ? coMention : aiOnly.length ? aiOnly : nonTrivial;
    const policy = coMention.length ? "co-mention human+ai" : aiOnly.length ? "fallback ai/agent" : "fallback non-trivial";
    return {
      pool: [...pool].sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || ""))),
      totals: {
        raw: all.length,
        nonTrivial: nonTrivial.length,
        coMention: coMention.length,
        aiOnly: aiOnly.length,
      },
      policy,
    };
  }

  function parseDate(raw) {
    if (!raw) return null;
    const iso = String(raw).replace(" ", "T").replace("+00:00", "Z");
    const dt = new Date(iso);
    return Number.isNaN(dt.getTime()) ? null : dt;
  }

  function sumLanguageShare(rows, scope) {
    return (rows || [])
      .filter((r) => r.scope === scope)
      .reduce((acc, r) => acc + (Number(r.share) || 0), 0);
  }

  function sumLanguageCount(rows, scope) {
    return (rows || [])
      .filter((r) => r.scope === scope)
      .reduce((acc, r) => acc + (Number(r.count) || 0), 0);
  }

  function buildCoherenceChecks({
    ontologyCooccurrence,
    transmission,
    language,
    coverage,
    totalPosts,
    totalComments,
    totalSubmolts,
    cooccurrenceLimit = 25,
    languageTolerance = 0.03,
  }) {
    const filteredPairs = (ontologyCooccurrence || [])
      .filter((r) => !isVariantPair(r.concept_a, r.concept_b))
      .slice(0, cooccurrenceLimit);
    const hasVariantInTop = filteredPairs.some((r) => isVariantPair(r.concept_a, r.concept_b));

    const txPolicy = buildTransmissionPool(transmission || []);
    const rebuiltTx = buildTransmissionPool(transmission || []);
    const txPolicyMatch = txPolicy.pool.length === rebuiltTx.pool.length && txPolicy.policy === rebuiltTx.policy;

    const postShare = sumLanguageShare(language, "posts");
    const commentShare = sumLanguageShare(language, "comments");
    const languageShareOk = Math.abs(postShare - 1) <= languageTolerance && Math.abs(commentShare - 1) <= languageTolerance;

    const postsMin = parseDate(coverage.posts_created_min);
    const postsMax = parseDate(coverage.posts_created_max);
    const commentsMin = parseDate(coverage.comments_created_min);
    const commentsMax = parseDate(coverage.comments_created_max);
    const postsRangeOk = Boolean(postsMin && postsMax && postsMin <= postsMax);
    const commentsRangeOk = Boolean(commentsMin && commentsMax && commentsMin <= commentsMax);
    const rangesOk = postsRangeOk && commentsRangeOk;

    const totalsOk = totalPosts > 0 && totalComments > 0;

    return {
      checks: [
        {
          name: "cooccurrence_without_variants",
          ok: !hasVariantInTop,
          detail: `${filteredPairs.length} filas; variantes en top=${hasVariantInTop ? "si" : "no"}`,
        },
        {
          name: "canonical_transmission_pool",
          ok: txPolicyMatch,
          detail: `${txPolicy.pool.length} filas; policy=${txPolicy.policy}`,
        },
        {
          name: "normalized_language_shares",
          ok: languageShareOk,
          detail: `posts=${postShare.toFixed(3)} / comments=${commentShare.toFixed(3)}`,
        },
        {
          name: "valid_time_ranges",
          ok: rangesOk,
          detail: `posts=${postsRangeOk ? "ok" : "fail"}, comments=${commentsRangeOk ? "ok" : "fail"}`,
        },
        {
          name: "non_empty_base_volume",
          ok: totalsOk,
          detail: `${totalSubmolts} submolts activos`,
        },
      ],
      transmission: txPolicy,
      language: { postShare, commentShare },
      ranges: { postsRangeOk, commentsRangeOk },
    };
  }

  const api = {
    DATA_BASE,
    TRANSMISSION_TEXT_MIN_CHARS,
    TRANSMISSION_HUMAN_RE,
    TRANSMISSION_AI_RE,
    CORE_CONCEPT_LEMMAS,
    CONCEPT_LEMMA_MAP,
    METRIC_CONTRACT_ROWS,
    CONFIDENCE_ROWS,
    coerceValue,
    parseCSVText,
    loadCSV,
    loadJSON,
    conceptLemma,
    isVariantPair,
    buildTransmissionPool,
    parseDate,
    sumLanguageShare,
    sumLanguageCount,
    buildCoherenceChecks,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  global.AnalyticsCore = api;
})(typeof globalThis !== "undefined" ? globalThis : window);
