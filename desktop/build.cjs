const { spawnSync } = require('node:child_process');

const target = process.argv[2] || 'dir';
const map = {
  dir: ['--dir'],
  windows: ['--win', 'portable', 'nsis'],
  linux: ['--linux', 'AppImage', 'deb'],
  mac: ['--mac', 'dmg', 'zip']
};
if (!map[target]) {
  console.error(`Unknown target: ${target}`);
  process.exit(1);
}
process.env.ELECTRON_BUILDER_COMPRESSION_LEVEL ||= '3';
const npx = process.platform === 'win32' ? 'npx.cmd' : 'npx';
const result = spawnSync(npx, ['electron-builder', ...map[target]], { stdio: 'inherit', env: process.env });
process.exit(result.status ?? 1);
