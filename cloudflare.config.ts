import { defineConfig } from 'cf/config';

export default defineConfig({
  worker: {
    name: 'taleloom',
    compatibilityDate: '2026-11-04',
    workersDev: true,
    previewUrls: true,
    // 与控制台一致：正式版与分支预览都挂在这个域名上，预览为 <预览名>.taleloom.zoranzhou.com。
    domains: [{ hostname: 'taleloom.zoranzhou.com', production: true, previews: true }],
    assets: { notFoundHandling: 'none' },
  },
});
