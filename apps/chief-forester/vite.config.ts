import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
  build: {
    // rayfin.yml points staticHosting at this folder.
    outDir: 'dist',
    sourcemap: false,
  },
});
