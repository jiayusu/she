"""vector.py — 情景库向量层: 确定性哈希嵌入 + FAISS 索引(numpy 兜底)。

嵌入器可插拔: 默认特征哈希(词 token + 中文字符 2/3-gram → 固定维 L2 归一),
确定性保证"SQLite 原始数据可重建索引"(FAISS 损坏对策, README §6 风险)。
生产可替换神经编码器, 只要保持 embed() 幂等即可复用重建链路。

索引 id 约定: 情景库热存储 = episode rowid(>0), 冷存储 = -rowid(<0),
一个索引同时服务跨天召回与冷存储再巩固检索(FR-M06)。
"""
import hashlib
import re
from pathlib import Path

import numpy as np

try:
    import faiss  # type: ignore
    HAS_FAISS = True
except ImportError:  # pragma: no cover - 环境无 faiss 时降级
    faiss = None
    HAS_FAISS = False

_TOKEN = re.compile(r"[a-z0-9']+")
_CJK = re.compile(r"[\u4e00-\u9fff]+")


def _features(text: str):
    text = text.strip().lower()
    feats = []
    for m in _TOKEN.findall(text):
        feats.append("w:" + m)
    for run in _CJK.findall(text):
        chars = list(run)
        feats.extend("c:" + ch for ch in chars)
        feats.extend("b:" + chars[i] + chars[i + 1] for i in range(len(chars) - 1))
        feats.extend("g:" + "".join(chars[i:i + 3]) for i in range(len(chars) - 2))
    return feats


def _hash_feat(feat: str, dim: int):
    h = hashlib.md5(feat.encode("utf-8")).digest()
    idx = int.from_bytes(h[:4], "little") % dim
    sign = 1.0 if h[4] & 1 else -1.0
    return idx, sign


class HashingEmbedder:
    """特征哈希嵌入: 快(<1ms)、确定性、零依赖。"""

    def __init__(self, dim: int = 256):
        self.dim = dim

    def embed(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        for feat in _features(text):
            idx, sign = _hash_feat(feat, self.dim)
            vec[idx] += sign
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec /= norm
        return vec

    def embed_many(self, texts) -> np.ndarray:
        return np.stack([self.embed(t) for t in texts]) if texts else \
            np.zeros((0, self.dim), dtype=np.float32)


class VectorIndex:
    """FAISS IndexIDMap2(IndexFlatIP) 优先, 无 faiss 时 numpy 全量内积兜底。"""

    def __init__(self, dim: int, use_faiss: bool = True):
        self.dim = dim
        self.backend = "faiss" if (use_faiss and HAS_FAISS) else "numpy"
        if self.backend == "faiss":
            base = faiss.IndexFlatIP(dim)
            self.index = faiss.IndexIDMap2(base)
        else:
            self._ids: list[int] = []
            self._vecs = np.zeros((0, dim), dtype=np.float32)

    def __len__(self):
        return len(self._ids) if self.backend == "numpy" else int(self.index.ntotal)

    def add(self, ids, vecs: np.ndarray):
        vecs = np.ascontiguousarray(vecs, dtype=np.float32)
        ids = np.asarray(ids, dtype=np.int64)
        if self.backend == "faiss":
            self.index.add_with_ids(vecs, ids)
        else:
            self._ids.extend(int(i) for i in ids)
            self._vecs = np.vstack([self._vecs, vecs])

    def remove(self, ids):
        ids = np.asarray(sorted({int(i) for i in ids}), dtype=np.int64)
        if not len(ids):
            return
        if self.backend == "faiss":
            self.index.remove_ids(ids)
        else:
            drop = set(ids.tolist())
            keep = [i for i, eid in enumerate(self._ids) if eid not in drop]
            self._ids = [self._ids[i] for i in keep]
            self._vecs = self._vecs[keep]

    def search(self, query_vec: np.ndarray, k: int):
        """返回 [(id, score)] 按分数降序; 不足 k 返回全部。"""
        qv = np.ascontiguousarray(query_vec.reshape(1, -1), dtype=np.float32)
        if len(self) == 0:
            return []
        k = min(k, len(self))
        if self.backend == "faiss":
            scores, ids = self.index.search(qv, k)
            return [(int(i), float(s)) for i, s in zip(ids[0], scores[0]) if i != -1]
        sims = self._vecs @ qv[0]
        order = np.argsort(-sims)[:k]
        return [(self._ids[int(i)], float(sims[int(i)])) for i in order]

    # ---- 持久化(快照/回滚/重建) ----
    def save(self, path):
        if self.backend == "faiss":
            faiss.write_index(self.index, str(path))
        else:
            np.savez(str(path) + ".npz", ids=np.array(self._ids, dtype=np.int64),
                     vecs=self._vecs)

    @classmethod
    def load(cls, path, dim: int, use_faiss: bool = True):
        if HAS_FAISS and use_faiss:
            index = cls(dim, use_faiss=True)
            index.index = faiss.read_index(str(path))
            return index
        data = np.load(str(path) + ".npz")
        index = cls(dim, use_faiss=False)
        index._ids = [int(i) for i in data["ids"]]
        index._vecs = data["vecs"]
        return index

    @classmethod
    def exists(cls, path, use_faiss: bool = True) -> bool:
        if HAS_FAISS and use_faiss:
            return path.exists()
        return Path(str(path) + ".npz").exists()
