// 会话状态:内存常驻;每次变更加 50ms 防抖落盘快照(模拟 04 记忆存储的会话备份接口),
// 崩溃/重启后从快照重建(非功能:恢复 ≤2s)。对话轮环形缓冲保留最近 40 轮,注入包取最近 10 轮。

import { mkdirSync, readFileSync, readdirSync, writeFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import type { Emotion, MinisterId, ScriptState, Turn } from './types.ts';

export const TURN_RING_CAPACITY = 40;
export const RECENT_TURNS_FOR_CTX = 10;

export interface SessionState {
  session_id: string;
  minister_on_duty: MinisterId;
  script_state: ScriptState;
  turns: Turn[];
  today_words: string[];
  emotion: Emotion;
  created_at: number;
  updated_at: number;
}

interface SessionSnapshot {
  version: 1;
  state: SessionState;
}

export class SessionManager {
  private sessions = new Map<string, SessionState>();
  private dirty = new Set<string>();
  private flushTimer: NodeJS.Timeout | null = null;

  constructor(private dataDir: string) {
    mkdirSync(join(dataDir, 'snapshots'), { recursive: true });
  }

  get(id: string): SessionState {
    let s = this.sessions.get(id);
    if (!s) {
      s = {
        session_id: id,
        minister_on_duty: 'xiaop',
        script_state: {},
        turns: [],
        today_words: [],
        emotion: { valence: 0, arousal: 0.5 },
        created_at: Date.now(),
        updated_at: Date.now(),
      };
      this.sessions.set(id, s);
    }
    return s;
  }

  has(id: string): boolean {
    return this.sessions.has(id);
  }

  list(): SessionState[] {
    return [...this.sessions.values()];
  }

  setMinister(id: string, minister: MinisterId): void {
    const s = this.get(id);
    s.minister_on_duty = minister;
    this.touch(id);
  }

  setEmotion(id: string, emotion: Emotion): void {
    const s = this.get(id);
    s.emotion = emotion;
    this.touch(id);
  }

  mergeScriptState(id: string, patch: ScriptState | undefined): void {
    if (!patch) return;
    const s = this.get(id);
    s.script_state = { ...s.script_state, ...patch };
    this.touch(id);
  }

  appendTurn(id: string, turn: Turn): void {
    const s = this.get(id);
    s.turns.push(turn);
    if (s.turns.length > TURN_RING_CAPACITY) {
      s.turns.splice(0, s.turns.length - TURN_RING_CAPACITY);
    }
    this.touch(id);
  }

  addTodayWord(id: string, word: string): boolean {
    const s = this.get(id);
    if (!word || s.today_words.includes(word)) return false;
    s.today_words.push(word);
    this.touch(id);
    return true;
  }

  /** 跨自然日清空"今日已学词"。 */
  rolloverDayIfNeeded(id: string): void {
    const s = this.sessions.get(id);
    if (!s) return;
    const day = new Date(s.updated_at).toDateString();
    if (day !== new Date().toDateString()) {
      s.today_words = [];
      this.touch(id);
    }
  }

  private touch(id: string): void {
    const s = this.sessions.get(id)!;
    s.updated_at = Date.now();
    this.dirty.add(id);
    this.scheduleFlush();
  }

  private scheduleFlush(): void {
    if (this.flushTimer) return;
    this.flushTimer = setTimeout(() => {
      this.flushTimer = null;
      this.flushSync();
    }, 50);
    this.flushTimer.unref?.();
  }

  flushSync(): void {
    for (const id of this.dirty) {
      const s = this.sessions.get(id);
      if (!s) continue;
      const snap: SessionSnapshot = { version: 1, state: s };
      try {
        writeFileSync(this.snapshotPath(id), JSON.stringify(snap), 'utf8');
      } catch {
        // 落盘失败不阻塞主流程;下次变更会重试
      }
    }
    this.dirty.clear();
  }

  private snapshotPath(id: string): string {
    return join(this.dataDir, 'snapshots', `${encodeURIComponent(id)}.json`);
  }

  /** 崩溃恢复:从快照重建会话。返回本次实际恢复的会话 id 列表。 */
  rebuild(id: string): SessionState | null {
    const p = this.snapshotPath(id);
    if (!existsSync(p)) return null;
    try {
      const snap = JSON.parse(readFileSync(p, 'utf8')) as SessionSnapshot;
      if (snap.version !== 1) return null;
      this.sessions.set(id, snap.state);
      this.rolloverDayIfNeeded(id);
      return snap.state;
    } catch {
      return null;
    }
  }

  rebuildAll(): string[] {
    const dir = join(this.dataDir, 'snapshots');
    if (!existsSync(dir)) return [];
    const restored: string[] = [];
    for (const f of readdirSync(dir)) {
      if (!f.endsWith('.json')) continue;
      const id = decodeURIComponent(f.slice(0, -'.json'.length));
      if (this.rebuild(id)) restored.push(id);
    }
    return restored;
  }
}
