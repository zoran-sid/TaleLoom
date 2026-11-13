import { spawnSync } from 'node:child_process';
import process from 'node:process';

const python = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
const result = spawnSync(python, ['-B', ...process.argv.slice(2)], { stdio: 'inherit' });
process.exit(result.status ?? 1);
