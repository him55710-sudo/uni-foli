import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { defineConfig, loadEnv } from 'vite';
import { visualizer } from 'rollup-plugin-visualizer';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  const shouldAnalyzeBundle = env.ANALYZE === 'true';

  return {
    plugins: [
      react(),
      tailwindcss(),
      ...(shouldAnalyzeBundle
        ? [visualizer({ open: false, filename: 'stats.html', gzipSize: true, brotliSize: true })]
        : []),
    ],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
        '@shared-contracts': path.resolve(__dirname, '../packages/shared-contracts/src'),
      },
    },
    server: {
      hmr: process.env.DISABLE_HMR !== 'true',
    },
    build: {
      chunkSizeWarningLimit: 2000,
      rollupOptions: {
        output: {
          manualChunks(id) {
            const normalizedId = id.split(path.sep).join('/');
            if (!normalizedId.includes('/node_modules/')) return undefined;

            if (normalizedId.includes('/@tiptap/') || normalizedId.includes('/prosemirror')) {
              return 'editor-core';
            }
            if (
              normalizedId.includes('/react/') ||
              normalizedId.includes('/react-dom/') ||
              normalizedId.includes('/react-router-dom/') ||
              normalizedId.includes('/scheduler/')
            ) {
              return 'react-vendor';
            }
            if (normalizedId.includes('/firebase/') || normalizedId.includes('/@firebase/')) {
              return 'firebase-vendor';
            }
            if (normalizedId.includes('/recharts/') || normalizedId.includes('/d3-')) {
              return 'charts-vendor';
            }
            if (
              normalizedId.includes('/react-markdown/') ||
              normalizedId.includes('/remark-') ||
              normalizedId.includes('/rehype-') ||
              normalizedId.includes('/unified/') ||
              normalizedId.includes('/micromark') ||
              normalizedId.includes('/katex/')
            ) {
              return 'markdown-vendor';
            }
            if (
              normalizedId.includes('/docx/') ||
              normalizedId.includes('/file-saver/') ||
              normalizedId.includes('/html2pdf.js/') ||
              normalizedId.includes('/canvas-confetti/')
            ) {
              return 'export-vendor';
            }
            if (normalizedId.includes('/lucide-react/') || normalizedId.includes('/motion/')) {
              return 'ui-vendor';
            }
            if (normalizedId.includes('/axios/')) {
              return 'http-vendor';
            }
            if (normalizedId.includes('/@google/genai/')) {
              return 'ai-vendor';
            }
            return undefined;
          },
        },
      },
    },
  };
});
