import { defineConfig } from 'vite';
import { cloudflare } from '@cloudflare/vite-plugin';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  publicDir: fileURLToPath(new URL('./.web-public', import.meta.url)),
  plugins: [cloudflare()],
  build: {
    outDir: fileURLToPath(new URL('./dist', import.meta.url)),
    emptyOutDir: true,
    rollupOptions: {
      // 文字版首页与影像模式样片两个页面。
      input: {
        main: fileURLToPath(new URL('./index.html', import.meta.url)),
        cinematic: fileURLToPath(new URL('./cinematic.html', import.meta.url)),
      },
    },
  },
});
