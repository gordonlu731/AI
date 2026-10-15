import {defineConfig} from 'vite';
export default defineConfig({
  base:'./',
  build:{target:'es2022',chunkSizeWarningLimit:3000,rollupOptions:{output:{manualChunks(id){if(id.includes('@dimforge'))return 'physics';if(id.includes('/three/'))return 'graphics';}}}},
  server:{host:'0.0.0.0',port:5173,strictPort:true},
  preview:{host:'0.0.0.0',port:4173,strictPort:true},
});
