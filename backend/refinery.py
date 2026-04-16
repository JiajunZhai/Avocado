import hashlib
import json
import os
import re
import uuid

import numpy as np
from dotenv import load_dotenv
from knowledge_paths import VECTOR_DB_PATH, ensure_knowledge_layout

load_dotenv()

# ChromaDB was dropped (Python 3.14 / pydantic friction). We keep a persistent
# JSON store. Retrieval: dense sentence embeddings (default when sentence-transformers
# is installed) or TF-IDF. Env: RAG_RETRIEVAL=auto|vector|tfidf, RAG_EMBEDDING_MODEL=...
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError:
    print("[WARN] Scikit-Learn not found. Run pip install scikit-learn. Falling back to memory-only.")
    TfidfVectorizer = None


def _docs_fingerprint(docs: list[str]) -> str:
    h = hashlib.sha256()
    for d in docs:
        h.update((d or "").encode("utf-8", errors="replace"))
        h.update(b"\x1e")
    return h.hexdigest()


def _region_score_bonus(meta: dict | None, boost_tokens: list[str] | None) -> float:
    """Lexical metadata boost so 'Japan' in insight aligns with docs tagged Japan / Korea, Global."""
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


class ScikitLearnLocalDB:
    def __init__(self, db_path: str | None = None):
        ensure_knowledge_layout()
        self.db_path = db_path or str(VECTOR_DB_PATH)
        self.docs = []
        self.metas = []
        self.vectorizer = TfidfVectorizer() if TfidfVectorizer else None
        self.rag_backend = "tfidf"
        self.embedding_model_id: str | None = None

        # Ensure directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.load()

    def save(self):
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump({"docs": self.docs, "metas": self.metas}, f, ensure_ascii=False)

    def load(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.docs = data.get("docs", [])
                    self.metas = data.get("metas", [])
            except Exception:
                pass

    def add(self, documents, metadatas, ids):
        self.docs.extend(documents)
        self.metas.extend(metadatas)
        self.save()
        print(f"[RAG] Local matrix DB added {len(documents)} records (total: {len(self.docs)}).")

    def _indexed_corpus(self) -> list[str]:
        """Augment each row with region tokens so short queries (e.g. 'Japan') overlap docs."""
        lines: list[str] = []
        for doc, meta in zip(self.docs, self.metas):
            region = (meta or {}).get("region") or ""
            extra = f" {region} {region.replace(',', ' ')}"
            lines.append(f"{doc}{extra}")
        return lines

    def query(self, query_texts, n_results=3, region_boost_tokens: list[str] | None = None):
        if not self.docs or not self.vectorizer:
            return {"documents": [[]], "metadatas": [[]], "scores": [[]]}

        indexed = self._indexed_corpus()
        tfidf_matrix = self.vectorizer.fit_transform(indexed)
        query_vecs = self.vectorizer.transform(query_texts)
        similarities = cosine_similarity(query_vecs, tfidf_matrix)

        batch_results: list[list[str]] = []
        batch_metas: list[list[dict]] = []
        batch_scores: list[list[float]] = []
        for _, sim_scores in enumerate(similarities):
            scores = np.array(sim_scores, dtype=float).copy()
            if region_boost_tokens:
                for i in range(len(self.docs)):
                    scores[i] += _region_score_bonus(
                        self.metas[i] if i < len(self.metas) else None,
                        region_boost_tokens,
                    )
            order = np.argsort(scores)[::-1][:n_results]
            results = [self.docs[int(i)] for i in order]
            metas = [
                self.metas[int(i)] if int(i) < len(self.metas) else {}
                for i in order
            ]
            top_scores = [float(scores[int(i)]) for i in order]
            batch_results.append(results)
            batch_metas.append(metas)
            batch_scores.append(top_scores)

        return {"documents": batch_results, "metadatas": batch_metas, "scores": batch_scores}


class EmbeddingLocalDB(ScikitLearnLocalDB):
    """
    Sentence-embedding retrieval (cosine on L2-normalized vectors).
    Caches matrices under the same directory as local_storage.json (e.g. local_storage.embeddings.npz).
    """

    def __init__(self, db_path: str | None = None):
        super().__init__(db_path=db_path)
        self.rag_backend = "embedding"
        self._doc_matrix: np.ndarray | None = None
        self._embed_fp: str | None = None
        self._st_model = None
        mid = os.getenv(
            "RAG_EMBEDDING_MODEL",
            "sentence-transformers/all-MiniLM-L6-v2",
        ).strip()
        self.embedding_model_id = mid

    def _embed_cache_path(self) -> str:
        base = os.path.splitext(self.db_path)[0]
        return f"{base}.embeddings.npz"

    def _invalidate_embedding_cache(self) -> None:
        self._doc_matrix = None
        self._embed_fp = None
        p = self._embed_cache_path()
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass

    def _get_sentence_model(self):
        if self._st_model is None:
            from sentence_transformers import SentenceTransformer

            self._st_model = SentenceTransformer(self.embedding_model_id or "sentence-transformers/all-MiniLM-L6-v2")
        return self._st_model

    def _ensure_vectors(self) -> None:
        if not self.docs:
            return
        fp = _docs_fingerprint(self.docs)
        if self._doc_matrix is not None and self._embed_fp == fp:
            return
        cache_path = self._embed_cache_path()
        if os.path.exists(cache_path):
            try:
                z = np.load(cache_path, allow_pickle=True)
                zfp = str(z["fingerprint"])
                vecs = z["vectors"]
                mid = str(z["model_id"]) if "model_id" in z.files else ""
                if (
                    zfp == fp
                    and vecs.shape[0] == len(self.docs)
                    and mid == (self.embedding_model_id or "")
                ):
                    self._doc_matrix = vecs.astype(np.float32, copy=False)
                    self._embed_fp = fp
                    return
            except Exception as e:
                print(f"[RAG] Embedding cache unreadable ({e}), rebuilding.")

        texts = self._indexed_corpus()
        model = self._get_sentence_model()
        emb = model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        self._doc_matrix = np.asarray(emb, dtype=np.float32)
        self._embed_fp = fp
        try:
            np.savez_compressed(
                cache_path,
                vectors=self._doc_matrix,
                fingerprint=fp,
                model_id=self.embedding_model_id or "",
            )
        except OSError as e:
            print(f"[RAG] Could not write embedding cache: {e}")

    def load(self) -> None:
        super().load()
        # Drop in-memory matrix only; on-disk .npz may still match after restart.
        self._doc_matrix = None
        self._embed_fp = None

    def add(self, documents, metadatas, ids):
        super().add(documents, metadatas, ids)
        self._invalidate_embedding_cache()

    def query(self, query_texts, n_results=3, region_boost_tokens: list[str] | None = None):
        if not self.docs:
            return {"documents": [[]], "metadatas": [[]], "scores": [[]]}
        try:
            self._ensure_vectors()
            if self._doc_matrix is None or self._doc_matrix.shape[0] != len(self.docs):
                raise RuntimeError("embedding matrix out of sync with docs")
            model = self._get_sentence_model()
            q_emb = model.encode(
                query_texts,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            qm = np.asarray(q_emb, dtype=np.float32)
            sims = np.dot(qm, self._doc_matrix.T)
            batch_results: list[list[str]] = []
            batch_metas: list[list[dict]] = []
            batch_scores: list[list[float]] = []
            for row in range(sims.shape[0]):
                scores = np.array(sims[row], dtype=float).copy()
                if region_boost_tokens:
                    for i in range(len(self.docs)):
                        scores[i] += _region_score_bonus(
                            self.metas[i] if i < len(self.metas) else None,
                            region_boost_tokens,
                        )
                order = np.argsort(scores)[::-1][:n_results]
                batch_results.append([self.docs[int(i)] for i in order])
                batch_scores.append([float(scores[int(i)]) for i in order])
                batch_metas.append(
                    [
                        self.metas[int(i)] if int(i) < len(self.metas) else {}
                        for i in order
                    ]
                )
            return {"documents": batch_results, "metadatas": batch_metas, "scores": batch_scores}
        except Exception as e:
            print(f"[RAG] Vector retrieval failed ({e}); falling back to TF-IDF.")
            return super().query(query_texts, n_results, region_boost_tokens)


def _create_knowledge_base() -> ScikitLearnLocalDB:
    ensure_knowledge_layout()
    mode = os.getenv("RAG_RETRIEVAL", "auto").strip().lower()
    force_tfidf = mode in ("tfidf", "sparse", "legacy", "0", "false", "no")
    force_vector = mode in ("vector", "embedding", "dense", "1", "true", "yes")

    if force_tfidf:
        return ScikitLearnLocalDB()

    if mode in ("auto", "") or force_vector:
        try:
            import sentence_transformers  # noqa: F401

            return EmbeddingLocalDB()
        except ImportError:
            print(
                "[RAG] sentence-transformers not installed; using TF-IDF. "
                "pip install sentence-transformers for vector retrieval."
            )
            return ScikitLearnLocalDB()

    return ScikitLearnLocalDB()


collection = _create_knowledge_base()
CHROMA_AVAILABLE = True  # local JSON + TF-IDF or embeddings

def distill_and_store(raw_text: str, source_url: str, year_quarter: str = "Unknown Date"):
    """
    Distills raw reports into atomic JSON insights and stores them in Vector Engine.
    Requires DeepSeek V3 for reasoning extraction.
    If raw_text is empty and source_url is provided, it attempts to scrape the URL.
    """
    from openai import OpenAI
    cloud_client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    ) if os.getenv("DEEPSEEK_API_KEY") else None

    if not cloud_client:
        raise Exception("DeepSeek API Key missing for distillation.")

    system_prompt = """
    You are a Master Mobile Game User Acquisition Strategist.
    I will provide you with a raw industry report, competitor analysis, or market research text.
    You must distill the core 'Creative Genes' (execution rules) out of it.
    Format your response STRICTLY as a JSON array of objects representing atomic insights.
    
    Each object must have:
    {
      "region": "<Target region this applies to, e.g., Japan, Global, MENA>",
      "style": "<Visual/Editing style category>",
      "logic": "<The exact visual execution rule>",
      "psychology": "<Psychological trigger reasoning>"
    }
    
    CRITICAL: Output ONLY valid JSON array starting with `[` and ending with `]`. No markdown wrappers.
    """

    if not raw_text.strip() and source_url.strip():
        try:
            import urllib.request
            from bs4 import BeautifulSoup
            req = urllib.request.Request(source_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                html = response.read().decode('utf-8')
                
                soup = BeautifulSoup(html, 'html.parser')
                # Remove non-content tags
                for tag in soup(["script", "style", "nav", "footer", "meta", "noscript", "header"]):
                    tag.decompose()
                
                raw_text = soup.get_text(separator=' ', strip=True)
        except Exception as e:
            raise Exception(f"Failed to scrape URL with BeautifulSoup: {e}")

    try:
        response = cloud_client.chat.completions.create(
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Extract UA creative genes from the following report:\n\n{raw_text[:8000]}"}
            ]
        )
        
        raw_output = response.choices[0].message.content
        # Regex to strip markdown backticks if any
        match = re.search(r'(\[.*\])', raw_output, re.DOTALL)
        if match:
            raw_output = match.group(1)
            
        insights = json.loads(raw_output)
        
        if not isinstance(insights, list):
            raise Exception("Distillation did not return a list.")
            
        documents = []
        metadatas = []
        ids = []
        
        for idx, insight in enumerate(insights):
            # The document to embed is the logic string and psychology combined
            doc_str = f"[{insight.get('region', 'Global')}] Style: {insight.get('style', '')} - {insight.get('logic', '')} (Why: {insight.get('psychology', '')})"
            documents.append(doc_str)
            metadatas.append({
                "source": source_url,
                "region": insight.get('region', 'Global'),
                "year_quarter": year_quarter
            })
            ids.append(str(uuid.uuid4()))
            
        if documents:
            collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            
        return {"success": True, "extracted_count": len(documents), "insights": insights}
        
    except Exception as e:
        print(f"Distillation failed: {e}")
        return {"success": False, "error": str(e)}

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


def retrieve_context_with_evidence(
    query_string: str,
    top_k: int = 3,
    *,
    supplement: str = "",
    region_boost_tokens: list[str] | None = None,
) -> tuple[str, list[str], list[dict]]:
    """
    Retrieval over local_storage.json: sentence embeddings (default) or TF-IDF (RAG_RETRIEVAL=tfidf).
    supplement: game brief + insight text so retrieval is not limited to opaque *_id strings.
    region_boost_tokens: e.g. ['Japan'] from region JSON `name` to prefer region-tagged rules.
    """
    try:
        full_q = " ".join(s for s in (query_string, supplement) if s).strip()
        if not full_q:
            full_q = query_string
        results = collection.query(
            query_texts=[full_q],
            n_results=top_k,
            region_boost_tokens=region_boost_tokens,
        )
        
        if not results or not results.get("documents") or not results["documents"][0]:
            return "", [], []
            
        retrieved_docs = results["documents"][0] # list of strings
        # ChromaDB meta map structure
        retrieved_metas = results["metadatas"][0] if results.get("metadatas") and results["metadatas"][0] else []
        retrieved_scores = results["scores"][0] if results.get("scores") and results["scores"][0] else []
        
        context = "[Market Context from Vector Intelligence]\n"
        citations = []
        evidence: list[dict] = []
        
        for i, doc in enumerate(retrieved_docs):
            context += f"- Context Rule {i+1}: {doc}\n"
            meta = retrieved_metas[i] if i < len(retrieved_metas) and retrieved_metas[i] is not None else {}
            if i < len(retrieved_metas) and retrieved_metas[i] is not None:
                source = meta.get("source", "Unknown Oracle Database")
                year_q = meta.get("year_quarter", "")
                cite = f"{source} ({year_q})" if year_q else source
                if cite not in citations:
                    citations.append(cite)
            score = float(retrieved_scores[i]) if i < len(retrieved_scores) else 0.0
            evidence.append(
                {
                    "rule": doc,
                    "source": meta.get("source", "Unknown Oracle Database"),
                    "year_quarter": meta.get("year_quarter", ""),
                    "match_score": round(score, 4),
                    "reason_tag": _reason_tag_from_doc(doc),
                }
            )
                    
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
) -> tuple[str, list[str]]:
    context, citations, _evidence = retrieve_context_with_evidence(
        query_string,
        top_k=top_k,
        supplement=supplement,
        region_boost_tokens=region_boost_tokens,
    )
    return context, citations

def get_collection_stats() -> dict:
    """Returns total rule count and the last 10 inserted intel items."""
    total = len(collection.docs)
    recent = []
    
    last_n = min(10, total)
    if last_n > 0:
        docs = collection.docs[-last_n:]
        metas = collection.metas[-last_n:]
        
        for i in range(last_n):
            idx = last_n - 1 - i # reverse order
            meta = metas[idx] or {}
            doc = docs[idx] or ""
            
            cat = meta.get("category", "")
            if cat.startswith("region_"):
                region = meta.get("element", "Region")
                tag = "Cultural"
            elif cat.startswith("style_"):
                region = "Global"
                tag = "Style"
            elif cat.startswith("logic_"):
                region = "Global"
                tag = "Mechanics"
            else:
                region = "Global"
                tag = cat or "General"
                
            recent.append({
                "id": str(i),
                "region": region,
                "tag": tag,
                "title": doc[:60] + "..." if len(doc) > 60 else doc,
                "time": meta.get("year_quarter", "N/A"),
                "link": meta.get("source", "#"),
                "source": "Oracle Vault",
                "stat": f"Rank {meta.get('score', 85)}"
            })
            
    return {
        "total_rules": total,
        "recent_intel": recent,
        "retrieval_backend": getattr(collection, "rag_backend", "tfidf"),
        "embedding_model": getattr(collection, "embedding_model_id", None),
    }
