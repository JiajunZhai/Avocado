"""Phase 26 / E — SQLite-backed knowledge store + hybrid retrieval.

Public surface (kept stable for ``main.py``):
    - ``distill_and_store(raw_text, source_url, year_quarter)``
    - ``retrieve_context(query_string, top_k, *, supplement, region_boost_tokens)``
    - ``retrieve_context_with_evidence(...)``
    - ``get_collection_stats()``
    - ``collection`` (module-level wrapper used by older tests)

Retrieval pipeline (``RAG_RETRIEVAL=hybrid`` default):
    Query (+ supplement) -> BM25 top-N (FTS5) | Vector top-N (SentenceTransformer)
        -> Reciprocal Rank Fusion (k = RAG_RRF_K)
        -> Region-boost (lexical metadata bonus — carries over from pre-E logic)
        -> MMR diversity selection (lambda = RAG_MMR_LAMBDA)
        -> Optional Cross-Encoder rerank (RAG_RERANK=on, lazy-loaded)
        -> Context composer (groups by reason_tag for the prompt)

All components degrade gracefully:
    - FTS5 unavailable        -> LIKE scan fallback
    - sentence-transformers   -> fall back to TF-IDF over the doc text
    - cross-encoder missing   -> rerank silently skipped
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

import numpy as np
from dotenv import load_dotenv

from db import execute, fetchall, fetchone, get_conn, has_fts_table
from knowledge_paths import (
    LEGACY_VECTOR_DB_PATH,
    VECTOR_DB_PATH,
    ensure_knowledge_layout,
)

load_dotenv()

# Keep TF-IDF available as an offline fallback for the vector branch.
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity as _sk_cosine
except ImportError:  # pragma: no cover
    TfidfVectorizer = None
    _sk_cosine = None


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def _env_mode() -> str:
    return (os.getenv("RAG_RETRIEVAL", "auto") or "").strip().lower()


def _hybrid_requested() -> bool:
    mode = _env_mode()
    if mode in {"tfidf", "sparse", "legacy", "0", "false", "no"}:
        return False
    return True  # auto / hybrid / vector / empty


def _top_n() -> int:
    try:
        return max(5, int(os.getenv("RAG_TOPN", "30")))
    except ValueError:
        return 30


def _rrf_k() -> int:
    try:
        return max(1, int(os.getenv("RAG_RRF_K", "60")))
    except ValueError:
        return 60


def _mmr_lambda() -> float:
    try:
        v = float(os.getenv("RAG_MMR_LAMBDA", "0.7"))
        return min(0.99, max(0.0, v))
    except ValueError:
        return 0.7


def _rerank_enabled() -> bool:
    return (os.getenv("RAG_RERANK", "off") or "").strip().lower() in {"on", "1", "true", "yes"}


def _rerank_model_id() -> str:
    return (os.getenv("RAG_RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2") or "").strip()


def _embed_model_id() -> str:
    return (
        os.getenv("RAG_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2") or ""
    ).strip() or "sentence-transformers/all-MiniLM-L6-v2"


# ---------------------------------------------------------------------------
# Region-boost (carry-over from pre-E refinery)
# ---------------------------------------------------------------------------


def _region_score_bonus(meta: dict | None, boost_tokens: list[str] | None) -> float:
    if not boost_tokens or not meta:
        return 0.0
    region_field = (meta.get("region") or "").lower()
    bonus = 0.0
    for raw in boost_tokens:
        t = (raw or "").strip().lower()
        if len(t) < 2:
            continue
        if t in region_field:
            bonus += 0.14
        for part in re.split(r"[,/&\s]+", region_field):
            part = part.strip()
            if part and (t in part or part in t):
                bonus += 0.08
    if "global" in region_field:
        bonus += 0.03
    return min(bonus, 0.28)


def _reason_tag_from_doc(doc: str) -> str:
    d = (doc or "").lower()
    if any(k in d for k in ("hook", "opening", "first 1-3", "first 1-2")):
        return "hook"
    if any(k in d for k in ("format", "9:16", "caption", "sound-off")):
        return "format"
    if any(k in d for k in ("edit", "cut", "pace", "rhythm")):
        return "editing"
    if any(k in d for k in ("challenge", "curiosity", "social proof", "fomo")):
        return "psychology"
    return "general"


# ---------------------------------------------------------------------------
# Knowledge store
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _doc_fp(text: str) -> str:
    return hashlib.sha1((text or "").encode("utf-8", errors="replace")).hexdigest()[:24]


def _doc_id_from_text(text: str, source: str) -> str:
    base = f"{source or ''}||{text or ''}"
    return hashlib.sha1(base.encode("utf-8", errors="replace")).hexdigest()[:20]


def _fts_enabled() -> bool:
    try:
        return has_fts_table()
    except Exception:
        return False


class KnowledgeStore:
    """Thin facade over the ``knowledge_docs`` / ``knowledge_vectors`` tables.

    Keeps the retrieval surface used elsewhere (``.docs`` / ``.metas`` /
    ``.query(...)``) so we can still expose a ``collection`` global for the
    rare caller that pokes at it directly.
    """

    def __init__(self) -> None:
        self._st_model = None
        self._cross_encoder = None
        self._cross_encoder_failed = False
        self._vector_matrix: Optional[np.ndarray] = None
        self._vector_doc_ids: list[str] = []
        self._tfidf_vectorizer = None
        self._tfidf_matrix = None
        self._tfidf_doc_ids: list[str] = []
        self.rag_backend = "hybrid" if _hybrid_requested() else "tfidf"
        self.embedding_model_id = _embed_model_id()

    # ----- cached materialised views (pulled from DB on demand) -----

    @property
    def docs(self) -> list[str]:
        rows = fetchall("SELECT doc_text FROM knowledge_docs ORDER BY created_at ASC")
        return [r["doc_text"] for r in rows]

    @property
    def metas(self) -> list[dict[str, Any]]:
        rows = fetchall(
            "SELECT source, region, year_quarter, category, meta_json FROM knowledge_docs ORDER BY created_at ASC"
        )
        out: list[dict[str, Any]] = []
        for r in rows:
            meta: dict[str, Any] = {
                "source": r["source"] or "",
                "region": r["region"] or "",
                "year_quarter": r["year_quarter"] or "",
            }
            if r["category"]:
                meta["category"] = r["category"]
            try:
                extra = json.loads(r["meta_json"] or "{}")
                if isinstance(extra, dict):
                    for k, v in extra.items():
                        meta.setdefault(k, v)
            except Exception:
                pass
            out.append(meta)
        return out

    # ----- ingest -----

    def _load_all(self) -> list[tuple[str, str, dict[str, Any]]]:
        rows = fetchall(
            "SELECT id, doc_text, source, region, year_quarter, category, meta_json FROM knowledge_docs ORDER BY created_at ASC"
        )
        out: list[tuple[str, str, dict[str, Any]]] = []
        for r in rows:
            meta: dict[str, Any] = {
                "source": r["source"] or "",
                "region": r["region"] or "",
                "year_quarter": r["year_quarter"] or "",
            }
            if r["category"]:
                meta["category"] = r["category"]
            try:
                extra = json.loads(r["meta_json"] or "{}")
                if isinstance(extra, dict):
                    for k, v in extra.items():
                        meta.setdefault(k, v)
            except Exception:
                pass
            out.append((r["id"], r["doc_text"], meta))
        return out

    def add(
        self,
        documents: Iterable[str],
        metadatas: Iterable[dict[str, Any]],
        ids: Iterable[str] | None = None,
    ) -> None:
        docs = list(documents)
        metas = list(metadatas)
        if ids is None:
            id_list = [
                _doc_id_from_text(doc, (meta or {}).get("source", ""))
                for doc, meta in zip(docs, metas)
            ]
        else:
            id_list = list(ids)
        now = _now()
        rows_docs: list[tuple[Any, ...]] = []
        for i, doc in enumerate(docs):
            meta = metas[i] if i < len(metas) else {}
            if not isinstance(meta, dict):
                meta = {}
            doc_id = id_list[i] if i < len(id_list) else _doc_id_from_text(doc, meta.get("source", ""))
            rows_docs.append(
                (
                    doc_id,
                    str(doc or ""),
                    str(meta.get("source") or ""),
                    str(meta.get("region") or ""),
                    str(meta.get("year_quarter") or ""),
                    str(meta.get("category") or ""),
                    json.dumps(meta, ensure_ascii=False),
                    _doc_fp(str(doc or "")),
                    now,
                )
            )
        conn = get_conn()
        conn.executemany(
            """
            INSERT OR IGNORE INTO knowledge_docs(id, doc_text, source, region, year_quarter, category, meta_json, fingerprint, created_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows_docs,
        )
        if _fts_enabled():
            conn.executemany(
                "INSERT OR IGNORE INTO knowledge_fts(doc_id, region, doc_text) VALUES(?, ?, ?)",
                [(r[0], r[3], r[1]) for r in rows_docs],
            )
        # Invalidate cached retrieval matrices; vectors are rebuilt lazily.
        self._vector_matrix = None
        self._vector_doc_ids = []
        self._tfidf_matrix = None
        self._tfidf_doc_ids = []
        print(f"[RAG] Ingested {len(rows_docs)} docs (total in DB: {self.count()}).")

    def count(self) -> int:
        row = fetchone("SELECT COUNT(*) AS n FROM knowledge_docs")
        return int(row["n"]) if row else 0

    def vector_count(self) -> int:
        row = fetchone("SELECT COUNT(*) AS n FROM knowledge_vectors")
        return int(row["n"]) if row else 0

    # ----- vector machinery -----

    def _get_sentence_model(self):
        if self._st_model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._st_model = SentenceTransformer(self.embedding_model_id)
            except Exception as exc:
                print(f"[RAG] sentence-transformers unavailable ({exc}); vector branch disabled.")
                self._st_model = False  # sentinel
        return self._st_model if self._st_model is not False else None

    def _ensure_vectors(self) -> None:
        if not _hybrid_requested():
            return
        items = self._load_all()
        if not items:
            self._vector_matrix = None
            self._vector_doc_ids = []
            return
        model = self._get_sentence_model()
        if model is None:
            return
        model_id = self.embedding_model_id
        rows = fetchall("SELECT doc_id, model_id, vec, dim FROM knowledge_vectors")
        existing: dict[str, tuple[int, np.ndarray]] = {}
        for r in rows:
            if r["model_id"] != model_id or r["vec"] is None:
                continue
            dim = int(r["dim"] or 0)
            if dim <= 0:
                continue
            try:
                vec = np.frombuffer(r["vec"], dtype=np.float32).reshape(dim)
                existing[r["doc_id"]] = (dim, vec)
            except Exception:
                continue

        missing_ids: list[str] = []
        missing_texts: list[str] = []
        for doc_id, text, meta in items:
            if doc_id in existing:
                continue
            region = (meta or {}).get("region", "")
            missing_ids.append(doc_id)
            missing_texts.append(f"{text} {region}")

        if missing_texts:
            try:
                new_vecs = model.encode(
                    missing_texts,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                )
            except Exception as exc:
                print(f"[RAG] Embedding encode failed ({exc}); skipping vector index.")
                return
            now = _now()
            rows_to_write = []
            for doc_id, vec in zip(missing_ids, new_vecs):
                arr = np.asarray(vec, dtype=np.float32)
                rows_to_write.append(
                    (
                        doc_id,
                        model_id,
                        _doc_fp(model_id + doc_id),
                        int(arr.shape[0]),
                        arr.tobytes(),
                        now,
                    )
                )
                existing[doc_id] = (int(arr.shape[0]), arr)
            get_conn().executemany(
                """
                INSERT INTO knowledge_vectors(doc_id, model_id, fingerprint, dim, vec, updated_at)
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(doc_id) DO UPDATE SET
                    model_id=excluded.model_id,
                    fingerprint=excluded.fingerprint,
                    dim=excluded.dim,
                    vec=excluded.vec,
                    updated_at=excluded.updated_at
                """,
                rows_to_write,
            )

        ordered_ids = [doc_id for doc_id, _, _ in items if doc_id in existing]
        if not ordered_ids:
            self._vector_matrix = None
            self._vector_doc_ids = []
            return
        dim = existing[ordered_ids[0]][0]
        matrix = np.zeros((len(ordered_ids), dim), dtype=np.float32)
        for i, doc_id in enumerate(ordered_ids):
            matrix[i] = existing[doc_id][1]
        self._vector_matrix = matrix
        self._vector_doc_ids = ordered_ids

    def _ensure_tfidf(self) -> None:
        if TfidfVectorizer is None:
            return
        items = self._load_all()
        if not items:
            self._tfidf_matrix = None
            self._tfidf_doc_ids = []
            return
        corpus = [
            f"{text} {(meta or {}).get('region', '')}"
            for _doc_id, text, meta in items
        ]
        try:
            self._tfidf_vectorizer = TfidfVectorizer()
            self._tfidf_matrix = self._tfidf_vectorizer.fit_transform(corpus)
            self._tfidf_doc_ids = [doc_id for doc_id, _, _ in items]
        except Exception as exc:  # pragma: no cover - scikit quirks
            print(f"[RAG] TF-IDF build failed: {exc}")
            self._tfidf_matrix = None
            self._tfidf_doc_ids = []

    # ----- retrieval primitives -----

    def _bm25_topn(self, query: str, n: int) -> list[tuple[str, float]]:
        if not query.strip():
            return []
        if _fts_enabled():
            try:
                rows = get_conn().execute(
                    """
                    SELECT doc_id, bm25(knowledge_fts) AS score
                    FROM knowledge_fts
                    WHERE knowledge_fts MATCH ?
                    ORDER BY score ASC
                    LIMIT ?
                    """,
                    (_fts_query_from(query), n),
                ).fetchall()
                out: list[tuple[str, float]] = []
                for r in rows:
                    s = float(r["score"] or 0.0)
                    # lower bm25 == better → convert to similarity-like monotone desc score.
                    out.append((r["doc_id"], 1.0 / (1.0 + max(0.0, s))))
                return out
            except Exception as exc:
                print(f"[RAG] FTS5 MATCH failed ({exc}); falling back to LIKE.")
        # LIKE fallback — rudimentary but deterministic.
        tokens = [t for t in re.split(r"\s+", query.lower()) if len(t) > 1]
        if not tokens:
            return []
        like = " OR ".join("LOWER(doc_text) LIKE ?" for _ in tokens)
        params = [f"%{t}%" for t in tokens]
        rows = get_conn().execute(
            f"SELECT id AS doc_id, doc_text FROM knowledge_docs WHERE {like} LIMIT ?",
            (*params, n),
        ).fetchall()
        scored: list[tuple[str, float]] = []
        for r in rows:
            text = (r["doc_text"] or "").lower()
            hits = sum(text.count(t) for t in tokens)
            scored.append((r["doc_id"], float(hits)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:n]

    def _vector_topn(self, query: str, n: int) -> list[tuple[str, float]]:
        if not query.strip() or not _hybrid_requested():
            return []
        self._ensure_vectors()
        if self._vector_matrix is None or not self._vector_doc_ids:
            return self._tfidf_topn(query, n)
        model = self._get_sentence_model()
        if model is None:
            return self._tfidf_topn(query, n)
        try:
            q_emb = model.encode([query], normalize_embeddings=True, show_progress_bar=False)
            qv = np.asarray(q_emb, dtype=np.float32)
            sims = np.dot(qv, self._vector_matrix.T)[0]
            order = np.argsort(sims)[::-1][:n]
            return [(self._vector_doc_ids[int(i)], float(sims[int(i)])) for i in order]
        except Exception as exc:
            print(f"[RAG] Vector query failed ({exc}); falling back to TF-IDF.")
            return self._tfidf_topn(query, n)

    def _tfidf_topn(self, query: str, n: int) -> list[tuple[str, float]]:
        self._ensure_tfidf()
        if self._tfidf_matrix is None or not self._tfidf_doc_ids or _sk_cosine is None:
            return []
        try:
            qv = self._tfidf_vectorizer.transform([query])
            sims = _sk_cosine(qv, self._tfidf_matrix)[0]
            order = np.argsort(sims)[::-1][:n]
            return [(self._tfidf_doc_ids[int(i)], float(sims[int(i)])) for i in order]
        except Exception:
            return []

    # ----- fusion + diversity + rerank -----

    @staticmethod
    def _rrf_fuse(
        ranked_lists: list[list[tuple[str, float]]],
        k: int,
    ) -> dict[str, float]:
        scores: dict[str, float] = {}
        for lst in ranked_lists:
            for rank, (doc_id, _) in enumerate(lst):
                scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
        return scores

    def _apply_region_boost(
        self,
        scores: dict[str, float],
        boost_tokens: list[str] | None,
        id_to_meta: dict[str, dict[str, Any]],
    ) -> dict[str, float]:
        if not boost_tokens:
            return scores
        boosted: dict[str, float] = {}
        for doc_id, s in scores.items():
            bonus = _region_score_bonus(id_to_meta.get(doc_id), boost_tokens)
            boosted[doc_id] = s + bonus
        return boosted

    def _mmr_select(
        self,
        fused_scores: dict[str, float],
        top_k: int,
        *,
        id_to_text: dict[str, str],
    ) -> list[str]:
        if not fused_scores:
            return []
        lam = _mmr_lambda()
        candidates = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)
        cand_ids = [c[0] for c in candidates[: max(top_k * 4, top_k)]]
        if not cand_ids:
            return []
        if len(cand_ids) <= top_k or TfidfVectorizer is None or _sk_cosine is None:
            return cand_ids[:top_k]
        try:
            vec = TfidfVectorizer().fit_transform([id_to_text.get(i, "") for i in cand_ids])
            sim_matrix = _sk_cosine(vec)
        except Exception:
            return cand_ids[:top_k]
        selected: list[str] = []
        selected_idx: list[int] = []
        remaining = list(range(len(cand_ids)))
        while remaining and len(selected) < top_k:
            best_idx = None
            best_score = -1e9
            for idx in remaining:
                relevance = fused_scores.get(cand_ids[idx], 0.0)
                if selected_idx:
                    max_sim = float(max(sim_matrix[idx, j] for j in selected_idx))
                else:
                    max_sim = 0.0
                score = lam * relevance - (1 - lam) * max_sim
                if score > best_score:
                    best_score = score
                    best_idx = idx
            if best_idx is None:
                break
            selected.append(cand_ids[best_idx])
            selected_idx.append(best_idx)
            remaining.remove(best_idx)
        return selected

    def _rerank_cross_encoder(
        self, query: str, doc_ids: list[str], id_to_text: dict[str, str]
    ) -> list[str]:
        if not _rerank_enabled() or self._cross_encoder_failed or not doc_ids:
            return doc_ids
        if self._cross_encoder is None:
            try:
                from sentence_transformers import CrossEncoder

                self._cross_encoder = CrossEncoder(_rerank_model_id())
            except Exception as exc:
                print(f"[RAG] Cross-encoder load failed ({exc}); rerank disabled.")
                self._cross_encoder_failed = True
                return doc_ids
        try:
            pairs = [(query, id_to_text.get(i, "")) for i in doc_ids]
            scores = self._cross_encoder.predict(pairs)
            order = np.argsort(np.asarray(scores))[::-1]
            return [doc_ids[int(i)] for i in order]
        except Exception as exc:
            print(f"[RAG] Cross-encoder predict failed ({exc}); keeping pre-rerank order.")
            return doc_ids

    # ----- public query -----

    def query(
        self,
        query_texts: list[str],
        n_results: int = 3,
        region_boost_tokens: list[str] | None = None,
    ) -> dict[str, list[list[Any]]]:
        items = self._load_all()
        if not items:
            return {"documents": [[]], "metadatas": [[]], "scores": [[]]}
        id_to_text = {doc_id: text for doc_id, text, _ in items}
        id_to_meta = {doc_id: meta for doc_id, _, meta in items}

        batch_docs: list[list[str]] = []
        batch_metas: list[list[dict[str, Any]]] = []
        batch_scores: list[list[float]] = []

        n_pool = _top_n()
        rrf_k = _rrf_k()

        for q in query_texts:
            q = str(q or "").strip()
            if not q:
                batch_docs.append([])
                batch_metas.append([])
                batch_scores.append([])
                continue

            bm25_ranked = self._bm25_topn(q, n_pool)
            vector_ranked = self._vector_topn(q, n_pool)
            if not bm25_ranked and not vector_ranked:
                vector_ranked = self._tfidf_topn(q, n_pool)

            fused = self._rrf_fuse([bm25_ranked, vector_ranked], k=rrf_k)
            fused = self._apply_region_boost(fused, region_boost_tokens, id_to_meta)

            picked = self._mmr_select(fused, top_k=n_results, id_to_text=id_to_text)
            picked = self._rerank_cross_encoder(q, picked, id_to_text)[: n_results]

            docs_out = [id_to_text.get(i, "") for i in picked]
            metas_out = [id_to_meta.get(i, {}) for i in picked]
            scores_out = [round(float(fused.get(i, 0.0)), 6) for i in picked]
            batch_docs.append(docs_out)
            batch_metas.append(metas_out)
            batch_scores.append(scores_out)

        return {"documents": batch_docs, "metadatas": batch_metas, "scores": batch_scores}


# ---------------------------------------------------------------------------
# FTS5 query helper
# ---------------------------------------------------------------------------


_FTS_TOKEN_RE = re.compile(r"[A-Za-z0-9\u4e00-\u9fff]+")


def _fts_query_from(query: str) -> str:
    """Turn a natural-language query into an FTS5 MATCH expression.

    - Each safe token becomes ``"token"*`` (prefix match) so short queries still
      retrieve rules.
    - CJK tokens are kept intact; symbols that FTS5 treats as operators are
      discarded to avoid ``syntax error`` at runtime.
    """
    tokens = _FTS_TOKEN_RE.findall(query or "")
    if not tokens:
        return ""
    safe = []
    for tok in tokens:
        tok = tok.strip()
        if len(tok) <= 1:
            continue
        safe.append(f'"{tok}"*')
    return " OR ".join(safe) if safe else ""


# ---------------------------------------------------------------------------
# Seeding legacy JSON corpus (one-shot)
# ---------------------------------------------------------------------------


def _seed_from_legacy_json(path: Path, store: KnowledgeStore) -> dict[str, Any]:
    if not path.exists():
        return {"seeded": False, "reason": "missing"}
    if store.count() > 0:
        return {"seeded": False, "reason": "already populated"}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"seeded": False, "reason": f"invalid JSON: {exc}"}
    docs = raw.get("docs") or []
    metas = raw.get("metas") or []
    if not isinstance(docs, list) or not docs:
        return {"seeded": False, "reason": "no docs"}
    if not isinstance(metas, list) or len(metas) != len(docs):
        metas = [{} for _ in docs]
    store.add(documents=docs, metadatas=metas)
    return {"seeded": True, "count": len(docs)}


# ---------------------------------------------------------------------------
# Module-level singleton + backwards-compatible API
# ---------------------------------------------------------------------------


def _build_store() -> KnowledgeStore:
    ensure_knowledge_layout()
    store = KnowledgeStore()
    # First-time seed from the git-tracked JSON corpus (if DB is empty).
    _seed_from_legacy_json(Path(VECTOR_DB_PATH), store)
    if store.count() == 0:
        _seed_from_legacy_json(Path(LEGACY_VECTOR_DB_PATH), store)
    return store


collection = _build_store()
CHROMA_AVAILABLE = True  # historical flag kept for callers


def ensure_seeded() -> dict[str, Any]:
    """Re-seed the knowledge corpus if the DB is currently empty.

    Called from ``main._bootstrap_storage`` so tests that swap ``DB_PATH``
    after-the-fact still end up with the seed corpus available for retrieval.
    """
    if collection.count() > 0:
        return {"seeded": False, "reason": "already populated"}
    res = _seed_from_legacy_json(Path(VECTOR_DB_PATH), collection)
    if not res.get("seeded"):
        res = _seed_from_legacy_json(Path(LEGACY_VECTOR_DB_PATH), collection)
    return res


def distill_and_store(raw_text: str, source_url: str, year_quarter: str = "Unknown Date"):
    """Distill a raw UA report into atomic insights and persist them."""
    from openai import OpenAI

    cloud_client = (
        OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        )
        if os.getenv("DEEPSEEK_API_KEY")
        else None
    )
    if not cloud_client:
        raise Exception("DeepSeek API Key missing for distillation.")

    system_prompt = """
    You are a Master Mobile Game User Acquisition Strategist.
    I will provide you with a raw industry report, competitor analysis, or market research text.
    You must distill the core 'Creative Genes' (execution rules) out of it.
    Format your response STRICTLY as a JSON array of objects representing atomic insights.

    Each object must have:
    {
      "tier": "<Assign Tier 1 (Gold Standard), Tier 2 (Competitive Intel), or Tier 3 (Platform Guidelines)>",
      "game_type": "<Game Genre/Type>",
      "region": "<Target region this applies to, e.g., Japan, Global, MENA>",
      "angle": "<Psychological Angle>",
      "performance_level": "<High, Mid, Low based on report>",
      "script_logic": {
        "hook": "<First 3 seconds hook>",
        "build_up": "<Body/Escalation>",
        "climax": "<Peak action/Payoff>",
        "cta": "<Call to action>"
      }
    }

    CRITICAL: Output ONLY valid JSON array starting with `[` and ending with `]`. No markdown wrappers.
    """

    if not raw_text.strip() and source_url.strip():
        try:
            import urllib.request

            from bs4 import BeautifulSoup

            req = urllib.request.Request(source_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as response:
                html = response.read().decode("utf-8")
                soup = BeautifulSoup(html, "html.parser")
                for tag in soup(["script", "style", "nav", "footer", "meta", "noscript", "header"]):
                    tag.decompose()
                raw_text = soup.get_text(separator=" ", strip=True)
        except Exception as e:
            raise Exception(f"Failed to scrape URL with BeautifulSoup: {e}")

    try:
        response = cloud_client.chat.completions.create(
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Extract UA creative genes from the following report:\n\n{raw_text[:8000]}"},
            ],
        )
        raw_output = response.choices[0].message.content
        match = re.search(r"(\[.*\])", raw_output, re.DOTALL)
        if match:
            raw_output = match.group(1)
        insights = json.loads(raw_output)
        if not isinstance(insights, list):
            raise Exception("Distillation did not return a list.")

        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []
        ids: list[str] = []
        for insight in insights:
            doc_str = (
                f"[{insight.get('region', 'Global')}] Style: {insight.get('style', '')} - "
                f"{insight.get('logic', '')} (Why: {insight.get('psychology', '')})"
            )
            documents.append(doc_str)
            metadatas.append(
                {
                    "source": source_url,
                    "region": insight.get("region", "Global"),
                    "year_quarter": year_quarter,
                }
            )
            ids.append(str(uuid.uuid4()))
        if documents:
            collection.add(documents=documents, metadatas=metadatas, ids=ids)
        return {"success": True, "extracted_count": len(documents), "insights": insights}
    except Exception as e:
        print(f"Distillation failed: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Query expansion + retrieval
# ---------------------------------------------------------------------------


def _factor_supplement(angle_id: str | None, region_id: str | None) -> str:
    """Build a richer retrieval query from a selected factor.

    - ``logic_steps`` and ``psychological_triggers`` hold the tactical
      vocabulary (e.g. "Zeigarnik", "Speedrun") that our corpus actually
      contains; joining them lifts BM25 recall for angle-only queries.
    - ``regional_adaptations[region]`` (if set) injects region-specific phrasing
      so FTS5 matches the region-tagged rules first.
    """
    if not angle_id:
        return ""
    try:
        from factors_store import read_insight

        data = read_insight(angle_id)
    except Exception:
        data = {}
    if not isinstance(data, dict):
        return ""
    parts: list[str] = []
    logic = data.get("logic_steps")
    if isinstance(logic, list):
        parts.extend(str(x) for x in logic[:4])
    psych = data.get("psychological_triggers")
    if isinstance(psych, list):
        parts.extend(str(x) for x in psych[:3])
    bridge = data.get("commercial_bridge")
    if isinstance(bridge, str) and bridge:
        parts.append(bridge)
    adaptations = data.get("regional_adaptations")
    if region_id and isinstance(adaptations, dict):
        hit = adaptations.get(region_id) or adaptations.get(str(region_id).upper())
        if isinstance(hit, str) and hit.strip():
            parts.append(hit)
    core_emotion = data.get("core_emotion")
    if isinstance(core_emotion, str) and core_emotion:
        parts.append(core_emotion)
    return " \n ".join(parts)


def retrieve_context_with_evidence(
    query_string: str,
    top_k: int = 3,
    *,
    supplement: str = "",
    region_boost_tokens: list[str] | None = None,
    angle_id: str | None = None,
    region_id: str | None = None,
) -> tuple[str, list[str], list[dict]]:
    """Hybrid retrieval with query expansion + reason-tag grouping.

    The ``supplement`` argument is preserved for callers that already compute
    their own context (compat with Phase 25 call sites). When ``angle_id`` /
    ``region_id`` are provided we additionally pull richer text from the
    matching factor JSON so the query carries concrete tactical vocabulary.
    """
    try:
        expansions = [s for s in (query_string, supplement) if s]
        factor_text = _factor_supplement(angle_id, region_id)
        if factor_text:
            expansions.append(factor_text)
        full_q = " \n ".join(expansions).strip() or query_string
        results = collection.query(
            query_texts=[full_q],
            n_results=top_k,
            region_boost_tokens=region_boost_tokens,
        )
        if not results or not results.get("documents") or not results["documents"][0]:
            return "", [], []

        retrieved_docs = results["documents"][0]
        retrieved_metas = results.get("metadatas", [[]])[0] if results.get("metadatas") else []
        retrieved_scores = results.get("scores", [[]])[0] if results.get("scores") else []

        citations: list[str] = []
        evidence: list[dict] = []
        grouped: dict[str, list[str]] = {}
        for i, doc in enumerate(retrieved_docs):
            meta = retrieved_metas[i] if i < len(retrieved_metas) and retrieved_metas[i] else {}
            source = meta.get("source", "Unknown Oracle Database") if isinstance(meta, dict) else "Unknown Oracle Database"
            year_q = meta.get("year_quarter", "") if isinstance(meta, dict) else ""
            cite = f"{source} ({year_q})" if year_q else source
            if cite and cite not in citations:
                citations.append(cite)
            score = float(retrieved_scores[i]) if i < len(retrieved_scores) else 0.0
            reason = _reason_tag_from_doc(doc)
            evidence.append(
                {
                    "rule": doc,
                    "source": source,
                    "year_quarter": year_q,
                    "match_score": round(score, 4),
                    "reason_tag": reason,
                }
            )
            grouped.setdefault(reason, []).append(doc)

        # Compose context grouped by reason_tag so the LLM can see why each
        # rule was retrieved.
        order = ["hook", "format", "editing", "psychology", "general"]
        lines = ["[Market Context from Vector Intelligence]"]
        counter = 0
        for tag in order:
            docs = grouped.get(tag) or []
            if not docs:
                continue
            lines.append(f"# {tag.capitalize()} signals")
            for d in docs:
                counter += 1
                lines.append(f"- Context Rule {counter}: {d}")
        context = "\n".join(lines) if counter else ""
        return context, citations, evidence
    except Exception as e:
        print(f"RAG Retrieval failed: {e}")
        return "", [], []


def retrieve_context(
    query_string: str,
    top_k: int = 3,
    *,
    supplement: str = "",
    region_boost_tokens: list[str] | None = None,
    angle_id: str | None = None,
    region_id: str | None = None,
) -> tuple[str, list[str]]:
    context, citations, _ = retrieve_context_with_evidence(
        query_string,
        top_k=top_k,
        supplement=supplement,
        region_boost_tokens=region_boost_tokens,
        angle_id=angle_id,
        region_id=region_id,
    )
    return context, citations


def rebuild_vectors() -> dict[str, Any]:
    """Admin helper — forces vector re-embedding for every row in the DB."""
    get_conn().execute("DELETE FROM knowledge_vectors")
    collection._vector_matrix = None
    collection._vector_doc_ids = []
    collection._ensure_vectors()
    return {
        "docs": collection.count(),
        "vectors": collection.vector_count(),
        "embedding_model": collection.embedding_model_id,
    }


def get_collection_stats() -> dict:
    total = collection.count()
    recent_rows = fetchall(
        "SELECT id, doc_text, source, region, year_quarter, category FROM knowledge_docs ORDER BY created_at DESC LIMIT 10"
    )
    recent: list[dict[str, Any]] = []
    for i, r in enumerate(recent_rows):
        cat = str(r["category"] or "")
        if cat.startswith("region_"):
            region = r["region"] or "Region"
            tag = "Cultural"
        elif cat.startswith("style_"):
            region = "Global"
            tag = "Style"
        elif cat.startswith("logic_"):
            region = "Global"
            tag = "Mechanics"
        else:
            region = r["region"] or "Global"
            tag = cat or "General"
        doc = r["doc_text"] or ""
        recent.append(
            {
                "id": str(i),
                "region": region,
                "tag": tag,
                "title": doc[:60] + "..." if len(doc) > 60 else doc,
                "time": r["year_quarter"] or "N/A",
                "link": r["source"] or "#",
                "source": "Oracle Vault",
                "stat": "Rank 85",
            }
        )
    return {
        "total_rules": total,
        "recent_intel": recent,
        "retrieval_backend": collection.rag_backend,
        "embedding_model": collection.embedding_model_id,
        "fts5": _fts_enabled(),
        "vectors": collection.vector_count(),
        "rerank": "on" if _rerank_enabled() else "off",
        "rerank_model": _rerank_model_id() if _rerank_enabled() else None,
    }
