// 入口:启动调度服务。数据目录 data/,配置目录 config/。

import { join } from 'node:path';
import { App } from './app.ts';
import { listen } from './server.ts';

const PORT = Number(process.env.PORT ?? 8787);
const DATA_DIR = process.env.DATA_DIR ?? join(process.cwd(), 'data');
const CONFIG_DIR = process.env.CONFIG_DIR ?? join(process.cwd(), 'config');

async function main(): Promise<void> {
  const app = new App({ dataDir: DATA_DIR, configDir: CONFIG_DIR });

  // 非功能:崩溃恢复后从记忆存储重建(≤2s)
  const recovery = app.recover();
  console.log(`[route] 会话恢复: ${recovery.restored} 个会话, 耗时 ${recovery.elapsed_ms.toFixed(1)}ms`);

  app.jobs.start();
  let info: Awaited<ReturnType<typeof listen>>;
  try {
    info = await listen(app, PORT);
  } catch (e) {
    const err = e as { code?: string };
    if (err.code === 'EADDRINUSE') {
      console.error(`[route] 端口 ${PORT} 已被占用,请换端口:PORT=${PORT + 1} npm start`);
      process.exit(1);
    }
    throw e;
  }
  console.log(`[route] 五大臣调度服务已启动`);
  console.log(`  POST /agent/dispatch   http://127.0.0.1:${info.port}/agent/dispatch`);
  console.log(`  WS   /agent/session    ws://127.0.0.1:${info.port}/agent/session`);
  console.log(`  健康检查               http://127.0.0.1:${info.port}/healthz`);
  console.log(`  管理端点               http://127.0.0.1:${info.port}/admin/*`);
  console.log(`  数据目录               ${DATA_DIR}`);

  const shutdown = (): void => {
    console.log('\n[route] 收到退出信号,flush 会话快照后退出');
    app.shutdown();
    void info.close().then(() => process.exit(0));
  };
  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);
}

void main().catch((e) => {
  console.error('[route] 启动失败:', e);
  process.exit(1);
});
