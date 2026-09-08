import { readdirSync } from 'node:fs';
import { spawnSync } from 'node:child_process';

const [directory, extension = 'ts'] = process.argv.slice(2);
const files = readdirSync(directory).filter(name => name.endsWith(`.test.${extension}`)).sort();
if (!files.length) throw new Error(`No tests found in ${directory}`);
const result = spawnSync(process.execPath, [
  ...(extension === 'ts' ? ['--import', 'tsx'] : []), '--test',
  ...files.map(name => `${directory}/${name}`),
], { stdio: 'inherit' });
if (result.error) throw result.error;
process.exit(result.status ?? 1);
