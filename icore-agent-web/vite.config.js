import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
        // SSE / 流式响应必须显式禁用上游压缩协商。Vite 底层的 http-proxy
        // 在看到 Content-Encoding: gzip 时会把响应整段缓冲到 gunzip 完成
        // 再发给浏览器，表现就是"后端一直在输出、前端等到结束才一次显示"。
        // 强制 Accept-Encoding: identity，后端就不会压缩，代理直接 pipe。
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq) => {
            proxyReq.setHeader('Accept-Encoding', 'identity')
          })
        },
      },
    },
  },
})
