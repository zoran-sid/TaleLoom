import { defineConfig } from 'cf/config';

export default defineConfig({
  worker: {
    name: 'taleloom',
    compatibilityDate: '2026-11-04',
    workersDev: true,
    previewUrls: true,
    assets: { notFoundHandling: 'none' },
  },
});
