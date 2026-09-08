// /api/see —— 视觉模块存根（PRD §7：视觉模块已有，此处为可独立运行的实现）。
// 优先调用真实 LLM（配置 SEE_LLM_URL 时），任何失败回落到模板回应（FR-P05：LLM 失败 → 模板回应）。
// bbox_hint {label} 直接用于组织儿童话术；无 label 时用通用模板。
import { templateReply } from '../web/js/replies.js';

function buildPrompt(label) {
  return (
    `你叫王冠，是给3-6岁孩子讲万物的伙伴。请用中文说1-2句话介绍"${label}"，` +
    `语气活泼、句子简短、带一个孩子能懂的小知识，不要用 emoji，不要 markdown。`
  );
}

async function callLlm(label, env, signal) {
  const res = await fetch(env.SEE_LLM_URL, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      ...(env.SEE_LLM_KEY ? { authorization: `Bearer ${env.SEE_LLM_KEY}` } : {}),
    },
    body: JSON.stringify({
      model: env.SEE_LLM_MODEL || 'gpt-4o-mini',
      messages: [{ role: 'user', content: buildPrompt(label) }],
      max_tokens: 120,
      temperature: 0.7,
    }),
    signal,
  });
  if (!res.ok) throw new Error(`llm http ${res.status}`);
  const data = await res.json();
  const text = data?.choices?.[0]?.message?.content?.trim();
  if (!text) throw new Error('llm empty');
  return text;
}

/**
 * @param {{label?:string, level?:string}} p
 * @param {NodeJS.ProcessEnv} env
 * @returns {Promise<{text, source}>} source: llm | template | template-fallback
 */
export async function generateReply(p = {}, env = process.env) {
  const label = p.label || '';
  // 测试开关：模拟 LLM 挂掉，验证模板兜底路径
  if (env.SEE_SIMULATE_LLM_FAIL === '1' && env.SEE_LLM_URL) {
    const tpl = templateReply(p);
    return { ...tpl, source: 'template-fallback' };
  }
  if (env.SEE_LLM_URL) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 8000);
    try {
      const text = await callLlm(label || '一个有趣的东西', env, ctrl.signal);
      return { text, source: 'llm' };
    } catch {
      const tpl = templateReply(p);
      return { ...tpl, source: 'template-fallback' };
    } finally {
      clearTimeout(timer);
    }
  }
  return templateReply(p);
}
