// FR-G02 验收:意图→大臣映射正确;映射表配置化、可热改;备选链与降级兜底生效。
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { DEFAULT_MINISTER_MAP, MapValidationError, MinisterMapTable, validateMinisterMap } from '../src/mapping.ts';
import { makeTestApp } from './util.ts';

describe('FR-G02 大臣映射表', () => {
  it('默认映射:六类意图 → 主大臣', () => {
    const table = new MinisterMapTable(DEFAULT_MINISTER_MAP);
    assert.equal(table.resolve('memory').minister, 'ahai');
    assert.equal(table.resolve('word').minister, 'laonie');
    assert.equal(table.resolve('comfort').minister, 'xingxing');
    assert.equal(table.resolve('chitchat').minister, 'xiaop');
    assert.equal(table.resolve('court').minister, 'xiaonao');
    assert.equal(table.resolve('object').minister, 'laonie');
    assert.ok(!table.resolve('memory').fallback_used);
  });

  it('主大臣降级 → 按备选链执行', () => {
    const table = new MinisterMapTable(DEFAULT_MINISTER_MAP);
    const r = table.resolve('memory', { degraded: new Set(['ahai']) });
    assert.equal(r.minister, 'laonie');
    assert.ok(r.fallback_used);
  });

  it('主大臣与备选全部降级 → 兜底小P', () => {
    const table = new MinisterMapTable(DEFAULT_MINISTER_MAP);
    const r = table.resolve('memory', { degraded: new Set(['ahai', 'laonie', 'xiaop']) });
    assert.equal(r.minister, 'xiaop');
    assert.ok(r.fallback_used);
    assert.ok(r.reason.includes('兜底'));
  });

  it('安抚(*)降级可由任何大臣执行', () => {
    const table = new MinisterMapTable(DEFAULT_MINISTER_MAP);
    const r = table.resolve('comfort', { degraded: new Set(['xingxing', 'xiaop', 'ahai', 'xiaonao']) });
    assert.equal(r.minister, 'laonie', '除主大臣外唯一可用的大臣应接管安抚');
    assert.ok(r.fallback_used);
  });

  it('从配置文件加载映射(运营改配置即生效)', () => {
    const t = makeTestApp();
    try {
      const customPath = join(t.configDir, 'minister-map.json');
      const custom = {
        version: 2,
        clarify_minister: 'xiaop',
        confidence_threshold: 0.6,
        intents: {
          ...DEFAULT_MINISTER_MAP.intents,
          chitchat: { primary: 'laonie', backups: ['xiaop'] },
        },
      };
      writeFileSync(customPath, JSON.stringify(custom));
      const table = new MinisterMapTable(DEFAULT_MINISTER_MAP);
      table.loadFile(customPath);
      assert.equal(table.resolve('chitchat').minister, 'laonie');
      assert.equal(table.threshold(), 0.6);
    } finally {
      t.dispose();
    }
  });

  it('非法映射被拒绝且保留旧表', () => {
    const t = makeTestApp();
    try {
      const badPath = join(t.configDir, 'bad-map.json');
      const table = new MinisterMapTable(DEFAULT_MINISTER_MAP);

      const bad = {
        ...DEFAULT_MINISTER_MAP,
        intents: { ...DEFAULT_MINISTER_MAP.intents, memory: { primary: 'yuchizhe', backups: [] } },
      };
      assert.throws(() => validateMinisterMap(bad), MapValidationError);

      writeFileSync(badPath, '{not json');
      assert.throws(() => table.loadFile(badPath), MapValidationError);
      assert.equal(table.resolve('memory').minister, 'ahai', '坏配置不得覆盖旧表');
    } finally {
      t.dispose();
    }
  });

  it('App 内映射热加载:改文件 → reload 生效,无需发版', async () => {
    const t = makeTestApp();
    try {
      const mapPath = join(t.configDir, 'minister-map.json');
      writeFileSync(mapPath, JSON.stringify(DEFAULT_MINISTER_MAP));
      const { App } = await import('../src/app.ts');
      const app2 = new App({ dataDir: join(t.dataDir, 'x'), configDir: t.configDir });
      try {
        assert.equal(app2.mapTable.resolve('memory').minister, 'ahai');
        const custom = {
          ...DEFAULT_MINISTER_MAP,
          intents: { ...DEFAULT_MINISTER_MAP.intents, memory: { primary: 'laonie', backups: ['xiaop'] } },
        };
        writeFileSync(mapPath, JSON.stringify(custom));
        await app2.reloadMap();
        assert.equal(app2.mapTable.resolve('memory').minister, 'laonie');
      } finally {
        app2.shutdown();
      }
    } finally {
      t.dispose();
    }
  });
});
