import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// 개발 서버(npm run dev)에서는 API와 로그인 설정을 배포된 주소에서 가져온다.
//   PROXY_TARGET=https://dxxxx.cloudfront.net npm run dev
const target = process.env.PROXY_TARGET;
const proxy = target
  ? { '/v1': { target, changeOrigin: true }, '/config.json': { target, changeOrigin: true } }
  : undefined;

export default defineConfig({
  plugins: [react()],
  server: { proxy },
  build: { assetsDir: 'assets', sourcemap: false },
});
