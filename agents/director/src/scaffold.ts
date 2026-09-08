import type { DirectRequest, ScaffoldProposal, ScaffoldLevel } from './types.ts';

export class ScaffoldAgent {
  propose(req: DirectRequest, distressed: boolean, expression: string): ScaffoldProposal {
    const attempts = req.recent_attempts ?? [];
    const failures = attempts.filter((attempt) => attempt.success === false).length;
    const successes = attempts.filter((attempt) => attempt.success === true).length;
    const level = (distressed ? 6 : Math.max(0, Math.min(6, 2 + failures - Math.min(successes, 2)))) as ScaffoldLevel;
    const words = expression.replace(/[.!?]+$/, '').split(/\s+/);
    const choice = expression.toLowerCase().includes('milk') ? 'Milk or water?' : expression.toLowerCase().includes('water') ? 'Water or milk?' : 'This one or that one?';
    const prompt = level >= 5 ? `Say: ${expression}` : level === 4 ? `${words.slice(0, -1).join(' ')} ___` : level === 3 ? `${words[0]} ...` : level === 2 ? choice : level === 1 ? `Listen: ${expression}` : `Your turn: ${words.at(-1)}`;
    return { scaffold_level: level, prompt_pattern: prompt, fallback_pattern: distressed ? 'You can just listen.' : `Let’s try: ${expression}`, max_attempts: distressed ? 1 : 2 };
  }
}
