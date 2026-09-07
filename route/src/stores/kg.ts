// 老颞语义层 KG(FR-G06 热更新接口 / FR-G04 事实校验的冲突来源)。
// 真实实现由 04 记忆存储提供;此处为本地 mock,接口签名即"KG 热更新接口"约定。

import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';

export interface KGFact {
  subject: string;
  predicate: string;
  object: string;
  ts: number;
  source: 'consolidated' | 'direct' | 'manual';
}

export interface KGWordNode {
  word: string;
  status: 'confirmed';
  first_seen: number;
  confirmed_at: number;
  examples: number; // 情景库中出现的次数
}

export interface PendingReviewFact extends KGFact {
  id: string;
  reason: string;
  existing_object: string;
}

export interface HotUpdatePayload {
  words?: Array<{ word: string; examples: number }>;
  facts?: Array<{ subject: string; predicate: string; object: string }>;
}

export class SemanticKG {
  private facts = new Map<string, KGFact>(); // key: subject|predicate|object
  private wordNodes = new Map<string, KGWordNode>();
  private pendingReview: PendingReviewFact[] = [];

  constructor(private dataDir: string) {
    this.load();
  }

  private file(): string {
    return join(this.dataDir, 'kg.json');
  }

  private load(): void {
    const f = this.file();
    if (!existsSync(f)) return;
    try {
      const data = JSON.parse(readFileSync(f, 'utf8')) as {
        facts: KGFact[];
        words: KGWordNode[];
      };
      for (const fact of data.facts ?? []) this.facts.set(factKey(fact), fact);
      for (const w of data.words ?? []) this.wordNodes.set(w.word, w);
    } catch {
      // KG 文件损坏时以空载启动
    }
  }

  private persist(): void {
    const f = this.file();
    mkdirSync(dirname(f), { recursive: true });
    writeFileSync(
      f,
      JSON.stringify({ facts: [...this.facts.values()], words: [...this.wordNodes.values()] }, null, 2),
      'utf8',
    );
  }

  assert(fact: Omit<KGFact, 'ts'>): void {
    this.facts.set(factKey(fact), { ...fact, ts: Date.now() });
    this.persist();
  }

  /** 事实校验(风险对策:记忆写入放大 LLM 幻觉)。与 KG 已有事实冲突 → true。 */
  checkConflict(fact: { subject: string; predicate: string; object: string }): { conflict: boolean; existing_object?: string } {
    for (const f of this.facts.values()) {
      if (f.subject === fact.subject && f.predicate === fact.predicate && f.object !== fact.object) {
        return { conflict: true, existing_object: f.object };
      }
    }
    return { conflict: false };
  }

  /** FR-G04:冲突事实入待审队列(走 04 冲突接口),不直接固化。 */
  submitForReview(fact: { subject: string; predicate: string; object: string }, existing: string): PendingReviewFact {
    const item: PendingReviewFact = {
      id: `pr_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      ...fact,
      ts: Date.now(),
      source: 'direct',
      reason: '与 KG 已有事实冲突,待人工审核',
      existing_object: existing,
    };
    this.pendingReview.push(item);
    this.persist();
    return item;
  }

  listPendingReview(): PendingReviewFact[] {
    return [...this.pendingReview];
  }

  resolvePendingReview(id: string, accept: boolean): boolean {
    const idx = this.pendingReview.findIndex((p) => p.id === id);
    if (idx < 0) return false;
    const [item] = this.pendingReview.splice(idx, 1);
    if (accept) {
      // 以新事实覆盖旧值
      for (const [k, f] of [...this.facts.entries()]) {
        if (f.subject === item.subject && f.predicate === item.predicate) this.facts.delete(k);
      }
      this.assert({ subject: item.subject, predicate: item.predicate, object: item.object, source: 'manual' });
    }
    this.persist();
    return true;
  }

  /** FR-G06 KG 热更新接口:巩固批次落库(词→语义层)。 */
  hotUpdate(payload: HotUpdatePayload): { words: number; facts: number } {
    let words = 0;
    let facts = 0;
    for (const w of payload.words ?? []) {
      if (this.wordNodes.has(w.word)) continue;
      this.wordNodes.set(w.word, {
        word: w.word,
        status: 'confirmed',
        first_seen: Date.now(),
        confirmed_at: Date.now(),
        examples: w.examples,
      });
      words++;
    }
    for (const f of payload.facts ?? []) {
      this.assert({ ...f, source: 'consolidated' });
      facts++;
    }
    if (words + facts > 0) this.persist();
    return { words, facts };
  }

  hasWord(word: string): boolean {
    return this.wordNodes.has(word);
  }

  getWord(word: string): KGWordNode | null {
    return this.wordNodes.get(word) ?? null;
  }

  words(): KGWordNode[] {
    return [...this.wordNodes.values()];
  }

  allFacts(): KGFact[] {
    return [...this.facts.values()];
  }

  query(subject: string): KGFact[] {
    return this.allFacts().filter((f) => f.subject === subject);
  }
}

function factKey(f: { subject: string; predicate: string; object: string }): string {
  return `${f.subject}|${f.predicate}|${f.object}`;
}
