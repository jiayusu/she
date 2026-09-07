#!/usr/bin/env python3
"""kg_embed.py — W3 嵌入检索: RotatE 底座 + FAISS 向量近邻 + PPR 图扩散(多跳)。

用法(对齐 READMD.md):
  python kg_embed.py train --db data/kg.db --dim 100 --epochs 300
  python kg_embed.py index
  python kg_embed.py query apple

图谱 <5,000 节点时向量效果差, 自动退回 kg.next_words() 规则版(--force-vector 可强制)。
server.py 通过 KGRetriever 类复用本模块(检索 / W4 增量局部训练 / FAISS 局部重建)。
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

# torch(libiomp) 与 faiss(libomp) 在 Windows 同进程加载会冲突, 允许共存(检索场景风险可控)
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kg  # noqa: E402

ROOT = Path(__file__).resolve().parent
EMB_DIR = ROOT / "data" / "embeddings"
MIN_NODES_FOR_VECTOR = 5000  # README: 图谱 <5000 节点时向量效果差


# ------------------------------------------------------------------ 数据加载
def load_triples(conn):
    rows = conn.execute(
        "SELECT head, rel, tail, weight FROM edges WHERE status='active'").fetchall()
    ents, rels = {}, {}
    for r in rows:
        for w in (r["head"], r["tail"]):
            if w not in ents:
                ents[w] = len(ents)
        if r["rel"] not in rels:
            rels[r["rel"]] = len(rels)
    h = np.array([ents[r["head"]] for r in rows], dtype=np.int64)
    r_ = np.array([rels[r["rel"]] for r in rows], dtype=np.int64)
    t = np.array([ents[r["tail"]] for r in rows], dtype=np.int64)
    w = np.array([r["weight"] for r in rows], dtype=np.float32)
    return (h, r_, t, w), ents, rels


# ------------------------------------------------------------------ RotatE 训练
def train_rotatete(db_path, dim, epochs, batch=8192, negs=8, lr=2e-3, gamma=0.5,
                   adv_temp=1.0, val_n=1000, log_every=25):
    import torch
    import torch.nn.functional as F
    torch.set_num_threads(max(1, (os.cpu_count() or 4) - 1))
    torch.manual_seed(7)
    np.random.seed(7)
    conn = kg.connect(db_path)
    (h, r, t, w), ents, rels = load_triples(conn)
    n_ent, n_rel = len(ents), len(rels)
    print(f"训练集: {len(h):,} 边 / {n_ent:,} 实体 / {n_rel} 关系 / dim={dim}", flush=True)

    eps = 2.0 / (dim ** 0.5)
    ent_re = torch.empty(n_ent, dim).uniform_(-eps, eps).requires_grad_(True)
    ent_im = torch.empty(n_ent, dim).uniform_(-eps, eps).requires_grad_(True)
    phase = torch.empty(n_rel, dim).uniform_(-np.pi, np.pi)
    rel_re = phase.cos().requires_grad_(True)
    rel_im = phase.sin().requires_grad_(True)
    opt = torch.optim.Adam([ent_re, ent_im, rel_re, rel_im], lr=lr)

    # 已知三元组哈希: 过滤破坏后恰好为真的假负例(IsA 等关系的头破坏会大量撞真边)
    known = np.unique(h.astype(np.int64) * 73856093 ^ r.astype(np.int64) * 19349663
                      ^ t.astype(np.int64) * 83492791)
    known_t = torch.from_numpy(known)
    h_t, r_t, t_t = (torch.from_numpy(x) for x in (h, r, t))
    w_t = torch.from_numpy(w)
    rng = np.random.default_rng(7)
    val_idx = rng.choice(len(h), size=min(val_n, len(h)), replace=False)
    val_mask = np.zeros(len(h), dtype=bool)
    val_mask[val_idx] = True
    train_idx = torch.from_numpy(np.where(~val_mask)[0])
    h_tr, r_tr, t_tr, w_tr = h_t[train_idx], r_t[train_idx], t_t[train_idx], w_t[train_idx]
    n_train = len(h_tr)

    def dist(hr_re, hr_im, t_re, t_im):
        # RotatE: ||h∘r - t||₂, 复数差模长平方求和后整体开方
        return torch.sqrt(((hr_re - t_re) ** 2 + (hr_im - t_im) ** 2 + 1e-12).sum(-1))

    t0 = time.time()
    for epoch in range(1, epochs + 1):
        perm = torch.randperm(n_train)
        epoch_loss = 0.0
        for i in range(0, n_train, batch):
            b = perm[i:i + batch]
            bh, br, bt, bw = h_tr[b], r_tr[b], t_tr[b], w_tr[b]
            n = len(b)
            # 负采样: 只破坏尾实体(1-N 关系头破坏假负例率高), 命中已知三元组则重采样
            cand_h = bh.unsqueeze(1).expand(n, negs)
            cand_t = torch.randint(0, n_ent, (n, negs))
            for _ in range(2):
                hs = (cand_h.long() * 73856093 ^ br.long().unsqueeze(1) * 19349663
                      ^ cand_t.long() * 83492791)
                clash = torch.isin(hs, known_t)
                if not clash.any():
                    break
                cand_t = torch.where(clash, torch.randint(0, n_ent, (n, negs)), cand_t)
            h_neg = cand_h.reshape(-1)
            t_neg = cand_t.reshape(-1)
            r_neg = br.repeat_interleave(negs)

            hr_re = ent_re[bh] * rel_re[br] - ent_im[bh] * rel_im[br]
            hr_im = ent_re[bh] * rel_im[br] + ent_im[bh] * rel_re[br]
            d_pos = dist(hr_re, hr_im, ent_re[bt], ent_im[bt])

            hrn_re = ent_re[h_neg] * rel_re[r_neg] - ent_im[h_neg] * rel_im[r_neg]
            hrn_im = ent_re[h_neg] * rel_im[r_neg] + ent_im[h_neg] * rel_re[r_neg]
            d_neg = dist(hrn_re, hrn_im, ent_re[t_neg], ent_im[t_neg]).view(n, negs)

            with torch.no_grad():  # 自对抗负采样权重(RotatE 论文: 按行 softmax)
                alpha = torch.softmax(-d_neg / adv_temp, dim=1)
            loss = -((F.logsigmoid(gamma - d_pos) * bw).mean()
                     + (F.logsigmoid(d_neg - gamma) * alpha).sum(1).mean())
            opt.zero_grad()
            loss.backward()
            opt.step()
            epoch_loss += float(loss) * n / n_train
        with torch.no_grad():  # 实体向量按行归一化(2*dim 实向量 L2=1, 复数旋转保持模长)
            norm = torch.sqrt((ent_re ** 2 + ent_im ** 2).sum(1, keepdim=True)) + 1e-12
            ent_re /= norm
            ent_im /= norm
        if epoch % log_every == 0 or epoch == 1 or epoch == epochs:
            mrr, hits = evaluate(ent_re, ent_im, rel_re, rel_im, h, r, t, val_idx)
            print(f"  epoch {epoch:>3}/{epochs} loss={epoch_loss:.3f} "
                  f"MRR={mrr:.3f} Hits@10={hits:.3f} ({time.time()-t0:.0f}s)", flush=True)

    EMB_DIR.mkdir(parents=True, exist_ok=True)
    out = EMB_DIR / "rotate.pt"
    torch.save({"ent_re": ent_re.detach(), "ent_im": ent_im.detach(),
                "rel_re": rel_re.detach(), "rel_im": rel_im.detach(),
                "ent_ids": ents, "rel_ids": rels, "dim": dim,
                "trained_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "epochs": epochs, "edges": len(h)}, out)
    print(f"已保存 {out} ({out.stat().st_size/1e6:.0f} MB)")
    conn.close()
    return out


def evaluate(ent_re, ent_im, rel_re, rel_im, h, r, t, val_idx, chunk=256):
    """验证集 MRR / Hits@10(全实体排序)。

    实体与 h∘r 的复数模长均为 1, 故 ||h∘r - t||² = 2 - 2·Re⟨h∘r, t⟩,
    排序等价于复数内积矩阵乘(内存 O(chunk×n_ent), 避免 O(chunk×n_ent×dim) 张量)。
    """
    import torch
    ranks = []
    with torch.no_grad():
        for s in range(0, len(val_idx), chunk):
            idx = val_idx[s:s + chunk]
            ih = torch.from_numpy(h[idx])
            ir = torch.from_numpy(r[idx])
            it = torch.from_numpy(t[idx])
            hr_re = ent_re[ih] * rel_re[ir] - ent_im[ih] * rel_im[ir]
            hr_im = ent_re[ih] * rel_im[ir] + ent_im[ih] * rel_re[ir]
            ip = hr_re @ ent_re.T + hr_im @ ent_im.T  # (c, n_ent)
            gold = ip.gather(1, it.unsqueeze(1))
            rank = (ip > gold).sum(1).float() + 1.0  # 距离越小 ⇔ 内积越大
            ranks.append(rank)
    ranks = torch.cat(ranks)
    return float((1.0 / ranks).mean()), float((ranks <= 10).float().mean())


# ------------------------------------------------------------------ FAISS 索引
def build_index():
    import torch
    import torch.nn.functional as F
    ck = torch.load(EMB_DIR / "rotate.pt", map_location="cpu", weights_only=False)
    vecs = np.hstack([ck["ent_re"].numpy(), ck["ent_im"].numpy()]).astype(np.float32)
    vecs /= (np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9)
    np.save(EMB_DIR / "vectors.npy", vecs)
    with open(EMB_DIR / "ent_ids.json", "w", encoding="utf-8") as f:
        json.dump(ck["ent_ids"], f, ensure_ascii=False)
    try:
        import faiss
        index = faiss.IndexIDMap2(faiss.IndexFlatIP(vecs.shape[1]))
        index.add_with_ids(vecs, np.arange(vecs.shape[0], dtype=np.int64))
        faiss.write_index(index, str(EMB_DIR / "faiss.idx"))
        print(f"FAISS 索引: {vecs.shape[0]:,} 实体 × {vecs.shape[1]} 维 → faiss.idx")
    except ImportError:
        print("!! faiss 不可用, 索引退化为 numpy 暴力检索(vectors.npy 已保存)")
    return vecs.shape[0]


# ------------------------------------------------------------------ 检索器(供 CLI 与 server 复用)
class KGRetriever:
    """FAISS 近邻 + PPR 图扩散 + (可选)LLM 重排; 含 W4 增量局部训练与局部索引重建。"""

    def __init__(self, db_path, emb_dir=EMB_DIR):
        import torch
        import torch.nn.functional as F  # noqa: F401
        self._torch = torch
        self.db_path = db_path
        self.emb_dir = Path(emb_dir)
        self.conn = kg.connect(db_path)
        ck = torch.load(self.emb_dir / "rotate.pt", map_location="cpu", weights_only=False)
        self.ent_ids = ck["ent_ids"]
        self.id2ent = {i: w for w, i in self.ent_ids.items()}
        self.rel_ids = ck["rel_ids"]
        self.dim = ck["dim"]
        self.ent_re = ck["ent_re"].numpy().copy()
        self.ent_im = ck["ent_im"].numpy().copy()
        self.rel_re = ck["rel_re"].numpy()
        self.rel_im = ck["rel_im"].numpy()
        self._refresh_vecs()
        self._faiss = None
        try:
            import faiss
            self._faiss = faiss.read_index(str(self.emb_dir / "faiss.idx"))
        except Exception:  # noqa: BLE001 — 无索引时退化为 numpy 暴力检索
            self._faiss = None
        self._adj = None  # PPR 稀疏邻接, 惰性构建

    # -- 内部
    def _refresh_vecs(self):
        self.vecs = np.hstack([self.ent_re, self.ent_im]).astype(np.float32)
        self.vecs /= (np.linalg.norm(self.vecs, axis=1, keepdims=True) + 1e-9)

    @property
    def n_entities(self):
        return len(self.ent_ids)

    # ---- FAISS 近邻
    def ann(self, word, k=64):
        if word not in self.ent_ids:
            return []
        v = self.vecs[self.ent_ids[word]:self.ent_ids[word] + 1]
        if self._faiss is not None:
            import faiss
            scores, ids = self._faiss.search(v, k)
            return [(int(i), float(s)) for i, s in zip(ids[0], scores[0]) if i != -1]
        sims = self.vecs @ v[0]
        top = np.argsort(-sims)[:k]
        return [(int(i), float(sims[i])) for i in top]

    # ---- PPR 图扩散(多跳)
    def _build_adj(self):
        import scipy.sparse as sp
        rows = self.conn.execute(
            "SELECT head, tail, weight FROM edges WHERE status='active'").fetchall()
        n, idx = self.n_entities, self.ent_ids
        r_, c_, v_ = [], [], []
        for row in rows:
            i, j = idx.get(row["head"]), idx.get(row["tail"])
            if i is None or j is None:
                continue
            w = float(row["weight"] or 1.0)
            r_.extend((i, j))
            c_.extend((j, i))
            v_.extend((w, w))
        adj = sp.csr_matrix((v_, (r_, c_)), shape=(n, n))
        outdeg = np.asarray(adj.sum(1)).ravel()
        outdeg[outdeg == 0] = 1.0
        self._adj = adj.multiply(1.0 / outdeg[:, None]).tocsr()

    def ppr(self, word, alpha=0.15, iters=24, k=64):
        if word not in self.ent_ids:
            return []
        if self._adj is None:
            self._build_adj()
        e0 = np.zeros(self.n_entities, dtype=np.float64)
        e0[self.ent_ids[word]] = 1.0
        p = e0.copy()
        for _ in range(iters):
            p = alpha * e0 + (1 - alpha) * (self._adj.T @ p)
        top = np.argsort(-p)[:k + 1]
        return [(int(i), float(p[i])) for i in top if i != self.ent_ids[word]][:k]

    # ---- 综合检索(带边溯源)
    def retrieve(self, query, top_k=8, ann_k=64, use_llm=False):
        t0 = time.perf_counter()
        q = query.strip().lower().replace(" ", "_")
        if q not in self.ent_ids:
            hits = [w for w in self.ent_ids if w.startswith(q + "_")][:3]
            return {"query": query, "found": False, "hint": hits, "words": [],
                    "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}
        cos = dict(self.ann(q, ann_k))
        pr = dict(self.ppr(q, k=ann_k))
        cand = set(cos) | set(pr)
        cand.discard(self.ent_ids[q])
        maxc, maxp = (max(cos.values()), max(pr.values())) if cos and pr else (1.0, 1.0)
        scored = sorted(((i, 0.45 * cos.get(i, 0.0) / maxc + 0.55 * pr.get(i, 0.0) / maxp)
                         for i in cand), key=lambda x: -x[1])
        short = scored[:max(top_k * 4, 40)]
        names = [self.id2ent[i] for i, _ in short]
        ph = ",".join("?" * len(names))
        edge_rows = self.conn.execute(
            f"SELECT head, rel, tail, weight FROM edges WHERE status='active' AND "
            f"((head IN ({ph}) AND tail=?) OR (tail IN ({ph}) AND head=?)) "
            f"ORDER BY weight DESC LIMIT 200",
            (*names, q, *names, q)).fetchall()
        direct = {}
        for e in edge_rows:
            other = e["tail"] if e["head"] == q else e["head"]
            direct.setdefault(other, []).append(f'{e["head"]} -{e["rel"]}-> {e["tail"]}')
        words = []
        for i, s in short:
            w = self.id2ent[i]
            row = self.conn.execute("SELECT level FROM words WHERE word=?", (w,)).fetchone()
            if row:
                words.append({"word": w, "score": round(s, 4),
                              "level": row["level"], "edges": direct.get(w, [])[:2]})
        words.sort(key=lambda x: -x["score"])
        top = words[:top_k]
        reranked = False
        if use_llm:
            try:
                import llm_client
                order = llm_client.rerank(q, top, top_k)
                top = sorted(top, key=lambda c: order.index(c["word"])
                             if c["word"] in order else 999)[:top_k]
                reranked = True
            except Exception:  # noqa: BLE001 — 重排是增强项, 失败退回原序
                pass
        return {"query": query, "found": True, "words": top, "reranked": reranked,
                "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}

    # ---- W4: IncLoRA 式局部训练 + FAISS 局部重建
    def ensure_entities(self, new_words):
        """新词冷启动: 用活跃邻居向量均值初始化, 并接入 FAISS 索引。

        返回新分配的实体 id 列表。新实体参与后续 incremental_train 局部微调。
        """
        added_ids = []
        rng = np.random.default_rng(7)
        for w in new_words:
            if w in self.ent_ids:
                continue
            nbrs = self.conn.execute(
                "SELECT CASE WHEN head=? THEN tail ELSE head END AS other "
                "FROM edges WHERE status='active' AND (head=? OR tail=?) LIMIT 64",
                (w, w, w)).fetchall()
            nb_ids = [self.ent_ids[r["other"]] for r in nbrs if r["other"] in self.ent_ids]
            if nb_ids:
                v = self.vecs[np.array(nb_ids)].mean(0)
            else:
                v = rng.normal(0, 0.01, self.vecs.shape[1]).astype(np.float32)
            # 不变量: len(ent_ids) == len(ent_re) == len(vecs), id 连续分配
            new_id = len(self.ent_ids)
            assert new_id == len(self.ent_re) == len(self.vecs), (
                f"实体 id 空间不一致: ids={len(self.ent_ids)} "
                f"re={len(self.ent_re)} vecs={len(self.vecs)}")
            self.ent_re = np.vstack([self.ent_re, v[:self.dim]])
            self.ent_im = np.vstack([self.ent_im, v[self.dim:]])
            self.ent_ids[w] = new_id
            self.id2ent[new_id] = w
            added_ids.append(new_id)
        if added_ids:
            self._refresh_vecs()
            self._adj = None
            if self._faiss is not None:
                import faiss
                ids = np.array(added_ids, dtype=np.int64)
                self._faiss.add_with_ids(self.vecs[ids], ids)
        return added_ids

    def incremental_train(self, affected_words, epochs=10, lr=2e-3, negs=8, batch=4096,
                          max_rows=120_000):
        """只解冻受影响实体行做少量梯度步(其余行梯度置零), 并局部重建索引。

        对应热更链中的 "IncLoRA 局部训练": 受影响实体 ≈ 低秩适配集,
        冻结主干嵌入只训局部; 训练三元组限采样(max_rows), 保证万级边热更分钟级完成。
        """
        import torch
        import torch.nn.functional as F
        torch.set_num_threads(max(1, (os.cpu_count() or 4) - 1))
        idx = self.ent_ids
        affected = [idx[w] for w in affected_words
                    if w in idx and idx[w] < len(self.ent_re)]
        if not affected:
            return 0
        rows = self.conn.execute(
            "SELECT head, rel, tail FROM edges WHERE status='active'").fetchall()
        rows = [(r["head"], r["tail"], r["rel"]) for r in rows
                if r["rel"] in self.rel_ids and r["head"] in idx and r["tail"] in idx
                and (r["head"] in affected_words or r["tail"] in affected_words)]
        if len(rows) > max_rows:  # 预算控制: 随机采样, 保证热更时限
            rng = np.random.default_rng(7)
            keep = rng.choice(len(rows), size=max_rows, replace=False)
            rows = [rows[i] for i in keep]
        if not rows:
            return 0
        h = np.array([idx[a] for a, _, _ in rows], dtype=np.int64)
        t = np.array([idx[b] for _, b, _ in rows], dtype=np.int64)
        r = np.array([self.rel_ids[c] for _, _, c in rows], dtype=np.int64)
        h, r, t = (torch.from_numpy(x) for x in (h, r, t))
        n_ent = len(self.ent_re)  # 向量矩阵行数 = 真实 id 空间上界

        er = self._torch.from_numpy(self.ent_re).clone().requires_grad_(True)
        ei = self._torch.from_numpy(self.ent_im).clone().requires_grad_(True)
        rr = self._torch.from_numpy(self.rel_re)
        ri = self._torch.from_numpy(self.rel_im)
        mask = torch.zeros(n_ent)
        mask[torch.tensor(affected)] = 1.0
        opt = torch.optim.Adam([er, ei], lr=lr)
        n = len(h)
        k_half = negs // 2
        for _ in range(epochs):
            perm = torch.randperm(n)
            for i in range(0, n, batch):
                b = perm[i:i + batch]
                bh, br, bt = h[b], r[b], t[b]
                m = len(b)
                neg_t = torch.randint(0, n_ent, (m * k_half,))
                neg_h = torch.randint(0, n_ent, (m * (negs - k_half),))
                h_neg = torch.cat([bh.repeat_interleave(k_half), neg_h])
                t_neg = torch.cat([neg_t, bt.repeat_interleave(negs - k_half)])
                r_neg = br.repeat_interleave(negs)
                hr_re = er[bh] * rr[br] - ei[bh] * ri[br]
                hr_im = er[bh] * ri[br] + ei[bh] * rr[br]
                d_pos = torch.sqrt(((hr_re - er[bt]) ** 2 +
                                    (hr_im - ei[bt]) ** 2 + 1e-12).sum(-1))
                hrn_re = er[h_neg] * rr[r_neg] - ei[h_neg] * ri[r_neg]
                hrn_im = er[h_neg] * ri[r_neg] + ei[h_neg] * rr[r_neg]
                d_neg = torch.sqrt(((hrn_re - er[t_neg]) ** 2 +
                                    (hrn_im - ei[t_neg]) ** 2 + 1e-12).sum(-1))
                loss = -(F.logsigmoid(0.5 - d_pos).mean() + F.logsigmoid(d_neg - 0.5).mean())
                opt.zero_grad()
                loss.backward()
                er.grad *= mask.unsqueeze(1)  # 局部化: 只更新受影响实体行
                ei.grad *= mask.unsqueeze(1)
                opt.step()
        with torch.no_grad():  # 受影响行恢复单位模长(按行)
            norm = torch.sqrt((er ** 2 + ei ** 2).sum(1, keepdim=True)) + 1e-12
            er_n, ei_n = er / norm, ei / norm
            aff = np.array(affected, dtype=np.int64)
            self.ent_re[aff] = er_n[aff].numpy()
            self.ent_im[aff] = ei_n[aff].numpy()
            self._refresh_vecs()
            self._adj = None
        self._reindex_partial(affected)
        return len(affected)

    def _reindex_partial(self, affected_ids):
        """FAISS 局部重建: remove_ids 受影响向量后按新向量重加。"""
        if self._faiss is None:
            return
        import faiss
        ids = np.array(affected_ids, dtype=np.int64)
        self._faiss.remove_ids(faiss.IDSelectorBatch(ids))
        self._faiss.add_with_ids(self.vecs[ids], ids)

    def persist_vectors(self):
        np.save(self.emb_dir / "vectors.npy", self.vecs)
        ck = self._torch.load(self.emb_dir / "rotate.pt", map_location="cpu",
                              weights_only=False)
        ck["ent_re"] = self._torch.from_numpy(self.ent_re)
        ck["ent_im"] = self._torch.from_numpy(self.ent_im)
        ck["ent_ids"] = dict(self.ent_ids)  # 热更新增实体的 id 映射必须落盘
        self._torch.save(ck, self.emb_dir / "rotate.pt")
        if self._faiss is not None:
            import faiss
            faiss.write_index(self._faiss, str(self.emb_dir / "faiss.idx"))

    def reset_from_disk(self):
        """回滚后重载全部内存态。"""
        self.__init__(self.db_path, self.emb_dir)  # noqa: PLC2801


# ------------------------------------------------------------------ CLI
def cmd_query(word, top, force_vector):
    db = ROOT / "data" / "kg.db"
    conn = kg.connect(db)
    n = conn.execute("SELECT COUNT(*) c FROM (SELECT head FROM edges WHERE status='active' "
                     "UNION SELECT tail FROM edges WHERE status='active')").fetchone()["c"]
    conn.close()
    if n < MIN_NODES_FOR_VECTOR and not force_vector:
        conn = kg.connect(db)
        print(f"!! 图谱 {n:,} 节点 < {MIN_NODES_FOR_VECTOR:,}, 向量效果差 → 退回规则版 next_words()")
        print("规则推荐:", kg.next_words(conn, word, top))
        conn.close()
        return
    ret = KGRetriever(db)
    out = ret.retrieve(word, top_k=top)
    if not out["found"]:
        print(f"“{word}”不在图中。建议: {out['hint']}")
        return
    print(f"query {word}  (延迟 {out['latency_ms']} ms)")
    for i, c in enumerate(out["words"], 1):
        edges = "; ".join(c["edges"]) or "(经由图扩散多跳关联)"
        print(f"  {i}. {c['word']:<18} score={c['score']:<7} "
              f"level={c['level']:<8} {edges}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    tr = sub.add_parser("train")
    tr.add_argument("--db", default=str(ROOT / "data" / "kg.db"))
    tr.add_argument("--dim", type=int, default=100)
    tr.add_argument("--epochs", type=int, default=300)
    tr.add_argument("--batch", type=int, default=8192)
    tr.add_argument("--negs", type=int, default=8)
    tr.add_argument("--lr", type=float, default=1e-3)
    sub.add_parser("index")
    q = sub.add_parser("query")
    q.add_argument("word")
    q.add_argument("--top", type=int, default=8)
    q.add_argument("--force-vector", action="store_true")
    args = ap.parse_args()
    if args.cmd == "train":
        train_rotatete(args.db, args.dim, args.epochs, args.batch, args.negs, args.lr)
    elif args.cmd == "index":
        build_index()
    else:
        cmd_query(args.word, args.top, args.force_vector)


if __name__ == "__main__":
    main()
