# Analysis Schema: Memetics, Ontología del Lenguaje, Sociologia

This schema defines the interpretables and derived signals used for memetic, ontological, and sociological analysis of Moltbook data. It is inspired by Echeverria's Ontología del Lenguaje, translated into operational signals.

**Unit Of Analysis**
- doc_id
- doc_type
- post_id
- parent_id
- author_id
- author_name
- author_karma
- author_followers
- author_following
- author_has_x_handle
- submolt
- submolt_display
- created_at
- upvotes
- downvotes
- comment_count
- url
- scrape_ts
- run_id
- thread_path
- depth

**Text Geometry**
- char_count
- token_count
- unique_token_ratio
- alpha_ratio
- upper_ratio
- digit_ratio
- question_marks
- exclamation_marks
- ellipsis

**Language And Script**
- lang
- lang_is_english
- script_latin_ratio
- script_cyrillic_ratio
- script_arabic_ratio
- script_cjk_ratio
- script_other_ratio
- script_total_letters
- script_mixed

**Speech Acts**
- act_request
- act_offer
- act_promise
- act_declaration
- act_judgment
- act_assertion
- act_acceptance
- act_rejection
- act_clarification
- act_question_mark

**Declarations**
- decl_yes
- decl_no
- decl_ignorance
- decl_gratitude
- decl_forgiveness
- decl_love
- decl_resignation

**Moods**
- mood_ambition
- mood_resignation
- mood_resentment
- mood_gratitude
- mood_wonder
- mood_fear
- mood_anger
- mood_joy
- mood_sadness
- mood_trust
- mood_curiosity

**Epistemic Markers**
- epistemic_hedge
- epistemic_certainty
- epistemic_evidence

**Interference And Prompting**
- interference_score
- interference_injection_hits
- interference_disclaimer_hits
- interference_code_fences
- interference_urls
- interference_emojis

**Human Incidence Signals**
- human_incidence_score
- human_refs
- prompt_refs
- tooling_refs

**Vector Space Matchmaking**
- For each post, compute top K nearest neighbors by cosine similarity in TF-IDF space.
- Output file includes doc_id, neighbor_id, score, doc_lang, neighbor_lang, shared_terms.

**Context Dataset (VSM)**
- `context_posts.jsonl/parquet` with `context_text` (post + top comments).
- `context_comments.jsonl/parquet` with `context_text` (post + parent chain + comment).

**Edges (Network Layer)**
- Mentions: `edges_mentions.csv` with src_id, target, position.
- Links: `edges_links.csv` with url, domain.
- Hashtags: `edges_hashtags.csv` with target tags.
- Replies: `edges_replies.csv` with comment -> parent links.
- Authorship: `edges_authorship.csv` with agent -> content links.

**Diffusion Metrics (Snapshots)**
- `diffusion_posts.csv` with run-level deltas, velocity, peak score.
- `diffusion_runs.csv` with run summaries.
- `diffusion_submolts.csv` with aggregate diffusion per submolt.

**Quantitative Sociology Metrics**
- `submolt_stats.csv`: posts/comments/authors per submolt.
- `author_stats.csv`: posts/comments/submolt diversity per author.
- `reply_graph_centrality.csv` and `reply_graph_communities.csv`.
- `mention_graph_centrality.csv` and `mention_graph_communities.csv`.

**Memetic Modeling Outputs**
- `meme_candidates.csv`: top lexical meme candidates (n-grams).
- `meme_timeseries_hourly.parquet`: hourly counts for memes.
- `meme_bursts.csv`: Kleinberg burst windows.
- `meme_survival.csv`: lifetime hours + entropy.
- `meme_classification.csv`: flash/persistent/local/cross.
- `semantic_clusters.csv`: top terms per semantic cluster.
- `meme_hawkes.csv`: discrete Hawkes parameters (mu/alpha/decay/branching).
- `meme_sir.csv`: SIR proxy metrics (mean_Rt, peak_Rt).
- `meme_survival_curve.csv` and `meme_hazard_curve.csv`: survival/hazard curves (if lifelines installed).

**Interpretation Notes**
- Speech acts and declarations are signals of coordination and commitment.
- Moods frame how agents interpret and act in conversations.
- Epistemic markers separate assertions from judgments or speculation.
- Interference and human incidence signals flag likely external prompting or human-led action.
- Script mix and language detection highlight emergent languages and code-switching.
