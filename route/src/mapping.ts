// FR-G02 大臣映射表:意图 → 主大臣 → 备选大臣。
// 映射来自 config/minister-map.json(运营可改、支持热加载,不发版);
// 安抚类用 "*" 表示任何大臣可降级执行;主大臣降级(不可用)时按序尝试备选,
// 全部不可用兜底到澄清大臣(小P),绝不空转。

import { readFileSync, watch } from 'node:fs';
import { INTENTS, MINISTERS, type Intent, type MinisterId } from './types.ts';

export interface IntentRoute {
  primary: MinisterId;
  backups: MinisterId[] | '*';
}

export interface MinisterMapCfg {
  version: number;
  clarify_minister: MinisterId;
  confidence_threshold: number;
  intents: Record<Intent, IntentRoute>;
}

export interface ResolveResult {
  minister: MinisterId;
  fallback_used: boolean;
  reason: string;
}

export class MapValidationError extends Error {}

export function validateMinisterMap(cfg: unknown): MinisterMapCfg {
  const m = cfg as MinisterMapCfg;
  if (!m || typeof m !== 'object') throw new MapValidationError('映射表必须是对象');
  if (!MINISTERS.includes(m.clarify_minister)) {
    throw new MapValidationError(`clarify_minister 非法: ${String(m.clarify_minister)}`);
  }
  if (typeof m.confidence_threshold !== 'number' || m.confidence_threshold < 0 || m.confidence_threshold > 1) {
    throw new MapValidationError('confidence_threshold 必须在 0..1');
  }
  if (!m.intents) throw new MapValidationError('缺少 intents');
  for (const intent of INTENTS) {
    const r = m.intents[intent];
    if (!r) throw new MapValidationError(`缺少意图映射: ${intent}`);
    if (!MINISTERS.includes(r.primary)) {
      throw new MapValidationError(`意图 ${intent} 的 primary 非法: ${String(r.primary)}`);
    }
    if (r.backups !== '*') {
      if (!Array.isArray(r.backups)) throw new MapValidationError(`意图 ${intent} 的 backups 必须为数组或 "*"`);
      for (const b of r.backups) {
        if (!MINISTERS.includes(b)) {
          throw new MapValidationError(`意图 ${intent} 的备选大臣非法: ${String(b)}`);
        }
      }
    }
  }
  return m;
}

export class MinisterMapTable {
  private cfg: MinisterMapCfg;
  private source: 'default' | 'file' = 'default';
  private loadedFrom: string | null = null;
  private watcher: import('node:fs').FSWatcher | null = null;

  constructor(cfg: MinisterMapCfg) {
    this.cfg = cfg;
  }

  get config(): MinisterMapCfg {
    return this.cfg;
  }

  get sourcePath(): string | null {
    return this.loadedFrom;
  }

  get sourceKind(): string {
    return this.source;
  }

  /** 从文件加载映射表;校验失败时保留旧表并抛错(运营改错不能打挂线上路由)。 */
  loadFile(path: string): MinisterMapCfg {
    let parsed: unknown;
    try {
      parsed = JSON.parse(readFileSync(path, 'utf8'));
    } catch (e) {
      throw new MapValidationError(`映射表文件解析失败: ${(e as Error).message}`);
    }
    const validated = validateMinisterMap(parsed);
    this.cfg = validated;
    this.source = 'file';
    this.loadedFrom = path;
    return validated;
  }

  /** 热加载:监听文件变更,运营改完即生效,无需发版/重启。 */
  watchFile(path: string, onChange?: (cfg: MinisterMapCfg) => void, onError?: (e: Error) => void): void {
    this.loadFile(path);
    this.watcher?.close();
    let timer: NodeJS.Timeout | null = null;
    this.watcher = watch(path, () => {
      // 编辑器保存常触发多次事件,做 100ms 防抖
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        try {
          const cfg = this.loadFile(path);
          onChange?.(cfg);
        } catch (e) {
          onError?.(e as Error);
        }
      }, 100);
    });
  }

  stopWatch(): void {
    this.watcher?.close();
    this.watcher = null;
  }

  reload(path?: string): MinisterMapCfg {
    const p = path ?? this.loadedFrom;
    if (!p) return this.cfg;
    return this.loadFile(p);
  }

  threshold(): number {
    return this.cfg.confidence_threshold;
  }

  resolve(
    intent: Intent,
    opts: { degraded?: ReadonlySet<MinisterId> } = {},
  ): ResolveResult {
    const degraded = opts.degraded ?? new Set<MinisterId>();
    const route = this.cfg.intents[intent];

    if (!degraded.has(route.primary)) {
      return { minister: route.primary, fallback_used: false, reason: `意图 ${intent} 主大臣` };
    }

    const candidates =
      route.backups === '*'
        ? MINISTERS.filter((m) => m !== route.primary)
        : route.backups;
    const hit = candidates.find((m) => !degraded.has(m));
    if (hit) {
      return {
        minister: hit,
        fallback_used: true,
        reason: `主大臣 ${route.primary} 降级,按备选链降级执行`,
      };
    }

    const ultimate = this.cfg.clarify_minister;
    return {
      minister: ultimate,
      fallback_used: true,
      reason: `意图 ${intent} 主大臣与全部备选均降级,兜底 ${ultimate} 澄清接待`,
    };
  }
}

export const DEFAULT_MINISTER_MAP: MinisterMapCfg = {
  version: 1,
  clarify_minister: 'xiaop',
  confidence_threshold: 0.55,
  intents: {
    court: { primary: 'xiaonao', backups: ['xiaop'] },
    memory: { primary: 'ahai', backups: ['laonie'] },
    word: { primary: 'laonie', backups: ['ahai'] },
    comfort: { primary: 'xingxing', backups: '*' },
    object: { primary: 'laonie', backups: ['ahai', 'xiaop'] },
    chitchat: { primary: 'xiaop', backups: ['ahai'] },
  },
};
