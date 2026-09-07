// FR-G08 工具边界:
//   MCP tool-call(LLM 自主调用):KG 查询、日程提醒、情景回忆等 —— 经 ToolGateway 白名单放行;
//   系统钩子(强制管线):内容过滤、情绪检测、注入检测 —— 服务端在 dispatch 前后强制执行,
//   不暴露给 LLM,任何通过提示词/工具名调用系统钩子的请求一律拒绝(ToolBoundaryError),
//   且请求参数无法关闭钩子(disable_hooks 等字段直接忽略)。
// 边界清单文档化见 docs/tool-boundary.md。

import { EventEmitter } from 'node:events';
import type { Emotion } from './types.ts';
import type { LexiconCfg } from './intent.ts';
import type { SemanticKG } from './stores/kg.ts';
import type { AuditLog } from './audit.ts';

export const SYSTEM_HOOKS = ['hook.content_filter', 'hook.emotion_detect', 'hook.injection_detect'] as const;
export type SystemHookName = (typeof SYSTEM_HOOKS)[number];

export class ToolBoundaryError extends Error {
  constructor(name: string) {
    super(`工具边界违规:"${name}" 是系统钩子,LLM 不可调用(FR-G08)。可用 MCP 工具见 GET /admin/tools`);
    this.name = 'ToolBoundaryError';
  }
}

export interface McpTool {
  name: string;
  description: string;
  handler: (args: Record<string, unknown>) => Promise<unknown> | unknown;
}

export interface HookResult {
  text: string;
  emotion?: Emotion;
  filtered: boolean;
  injection_suspected: boolean;
}

// 内容过滤词表(内容安全钩子(05)在本模块的最小实现;完整实现见 05)
export const CONTENT_FILTER_LIST = ['暴力', '自杀', '血腥', '脏话占位词'];

export function filterContent(text: string): { text: string; filtered: boolean } {
  let filtered = false;
  let out = text;
  for (const w of CONTENT_FILTER_LIST) {
    if (out.includes(w)) {
      out = out.split(w).join('*'.repeat(Math.min(6, Math.max(2, w.length))));
      filtered = true;
    }
  }
  return { text: out, filtered };
}

export class ToolGateway {
  private tools = new Map<string, McpTool>();
  private injectionPatterns: RegExp[] = [];

  constructor(
    private kg: SemanticKG,
    private lexiconCfg: LexiconCfg,
    private audit: AuditLog,
    private bus: EventEmitter,
  ) {
    this.compileInjection();
    this.registerBuiltinTools();
  }

  reloadLexicon(cfg: LexiconCfg): void {
    this.lexiconCfg = cfg;
    this.compileInjection();
  }

  private compileInjection(): void {
    const patterns = this.lexiconCfg.injection_patterns ?? [];
    this.injectionPatterns = patterns
      .map((p) => {
        try {
          return new RegExp(p, 'i');
        } catch {
          return null;
        }
      })
      .filter((r): r is RegExp => r !== null);
  }

  private registerBuiltinTools(): void {
    this.register({
      name: 'kg.query',
      description: '查询语义知识库某主体的事实(老颞)',
      handler: (args) => {
        const subject = String(args.subject ?? '');
        return this.kg.query(subject);
      },
    });
    this.register({
      name: 'kg.related_words',
      description: '查询已巩固的语义词表(老颞)',
      handler: () => this.kg.words(),
    });
    this.register({
      name: 'schedule.reminder',
      description: '登记日程提醒(写入 working 库,由小P执行)',
      handler: (args) => ({ accepted: true, what: args.what ?? '', when: args.when ?? '' }),
    });
  }

  register(tool: McpTool): void {
    if (tool.name.startsWith('hook.')) {
      throw new Error(`不允许注册系统钩子前缀的工具: ${tool.name}`);
    }
    this.tools.set(tool.name, tool);
  }

  listMcpTools(): Array<{ name: string; description: string }> {
    return [...this.tools.values()].map((t) => ({ name: t.name, description: t.description }));
  }

  listSystemHooks(): Array<{ name: string; description: string; mandatory: true }> {
    return [
      { name: 'hook.content_filter', description: '内容过滤:输入与输出双向强制过滤', mandatory: true },
      { name: 'hook.emotion_detect', description: '情绪检测:声学情绪分归一化入上下文', mandatory: true },
      { name: 'hook.injection_detect', description: '提示词注入检测:命中则标记安全态', mandatory: true },
    ];
  }

  /** LLM 侧工具调用入口:系统钩子一律拒绝,与提示词内容无关(边界在代码层,不可被注入绕过)。 */
  async llmInvoke(name: string, args: Record<string, unknown> = {}): Promise<unknown> {
    if ((SYSTEM_HOOKS as readonly string[]).includes(name)) {
      this.audit.append({ ts: Date.now(), type: 'tool_invoke', detail: { name, blocked: true } });
      throw new ToolBoundaryError(name);
    }
    const tool = this.tools.get(name);
    if (!tool) {
      this.audit.append({ ts: Date.now(), type: 'tool_invoke', detail: { name, blocked: true, reason: 'unknown' } });
      throw new Error(`未知 MCP 工具: ${name}`);
    }
    this.audit.append({ ts: Date.now(), type: 'tool_invoke', detail: { name, blocked: false } });
    this.bus.emit('tool_invoke', { name });
    return await tool.handler(args);
  }

  detectInjection(text: string): boolean {
    if (!text) return false;
    return this.injectionPatterns.some((re) => re.test(text));
  }

  /** 输入侧强制钩子链:注入检测 → 情绪检测 → 内容过滤。 */
  runInputHooks(text: string, emotion?: Emotion): HookResult {
    const injection = this.detectInjection(text);
    const { text: filtered, filtered: hit } = filterContent(text);
    return { text: filtered, emotion, filtered: hit, injection_suspected: injection };
  }

  /** 输出侧强制钩子:内容过滤无条件执行(不接受任何"关闭"指令)。 */
  runOutputHooks(text: string): { text: string; filtered: boolean } {
    return filterContent(text);
  }
}
