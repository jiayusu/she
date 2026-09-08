import { randomUUID } from 'node:crypto';
import { existsSync, readFileSync } from 'node:fs';
import type { AsrMeta, Emotion } from './types.ts';

export function newId(prefix = ''): string {
  return prefix + randomUUID();
}

export function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v));
}

// 粗粒度 token 估算:CJK 字符(含中文标点)按 1 token,其余按 4 字符≈1 token。
// 仅用于预算控制,不追求与具体分词器对齐。
export function estimateTokens(s: string): number {
  let cjk = 0;
  let other = 0;
  for (const ch of s) {
    if (/[\u3000-\u9fff\uf900-\ufaff\uff00-\uffef]/.test(ch)) cjk++;
    else other++;
  }
  return cjk + Math.ceil(other / 4);
}

export function percentile(sortedAsc: number[], p: number): number {
  if (sortedAsc.length === 0) return 0;
  const idx = clamp(Math.ceil(p * sortedAsc.length) - 1, 0, sortedAsc.length - 1);
  return sortedAsc[idx]!;
}

export function dayOf(ts: number): string {
  return new Date(ts).toISOString().slice(0, 10);
}

export function normalizeEmotion(e: number | Partial<Emotion> | undefined): Emotion {
  if (typeof e === 'number') return { valence: clamp(e, -1, 1), arousal: 0.5 };
  if (!e) return { valence: 0, arousal: 0.5 };
  return {
    valence: clamp(e.valence ?? 0, -1, 1),
    arousal: clamp(e.arousal ?? 0.5, 0, 1),
    label: e.label,
  };
}

export function normalizeAsr(a: AsrMeta | number | undefined): AsrMeta {
  if (typeof a === 'number') return { conf: clamp(a, 0, 1) };
  if (!a) return {};
  return { conf: a.conf !== undefined ? clamp(a.conf, 0, 1) : undefined, lang: a.lang };
}

export interface JsonlLine {
  [k: string]: unknown;
}

export async function appendJsonl(file: string, line: JsonlLine): Promise<void> {
  const { appendFile, mkdir } = await import('node:fs/promises');
  const { dirname } = await import('node:path');
  await mkdir(dirname(file), { recursive: true });
  await appendFile(file, JSON.stringify(line) + '\n', 'utf8');
}

export function readJsonlSync(file: string): JsonlLine[] {
  if (!existsSync(file)) return [];
  const out: JsonlLine[] = [];
  for (const raw of readFileSync(file, 'utf8').split('\n')) {
    const t = raw.trim();
    if (!t) continue;
    try {
      out.push(JSON.parse(t) as JsonlLine);
    } catch {
      // 跳过损坏行,审计/存储文件允许尾部半行(崩溃场景)
    }
  }
  return out;
}

export function readJsonSync<T>(file: string): T | null {
  if (!existsSync(file)) return null;
  try {
    return JSON.parse(readFileSync(file, 'utf8')) as T;
  } catch {
    return null;
  }
}

export async function writeJson(file: string, data: unknown): Promise<void> {
  const { writeFile, mkdir } = await import('node:fs/promises');
  const { dirname } = await import('node:path');
  await mkdir(dirname(file), { recursive: true });
  await writeFile(file, JSON.stringify(data, null, 2), 'utf8');
}

export function now(): number {
  return Date.now();
}
