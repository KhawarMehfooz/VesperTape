import { expect, test } from '@playwright/test'
import { createServer as createHttpServer } from 'node:http'
import type { AddressInfo } from 'node:net'
import { createServer, loadConfigFromFile } from 'vite'

test('development proxy preserves Host and browser origin for API security checks', async ({ request }) => {
  const backend = createHttpServer((req, res) => {
    res.setHeader('Content-Type', 'application/json')
    res.end(JSON.stringify({ host: req.headers.host, origin: req.headers.origin }))
  })
  await new Promise<void>(resolve => backend.listen(0, '127.0.0.1', resolve))
  let vite: Awaited<ReturnType<typeof createServer>> | undefined
  try {
    const loaded = await loadConfigFromFile({ command: 'serve', mode: 'development' })
    const rule = loaded!.config.server!.proxy!['/api']
    const target = `http://127.0.0.1:${(backend.address() as AddressInfo).port}`
    vite = await createServer({ ...loaded!.config, configFile: false,
      server: { host: '127.0.0.1', port: 0, proxy: {
        '/api': typeof rule === 'string' ? target : { ...rule, target },
      } },
    })
    await vite.listen()
    const host = `127.0.0.1:${(vite.httpServer!.address() as AddressInfo).port}`
    for (const origin of [`http://${host}`, 'https://untrusted.example']) {
      const response = await request.post(`http://${host}/api/preview`, {
        headers: { Origin: origin }, data: {},
      })
      expect(await response.json()).toEqual({ host, origin })
    }
  } finally {
    await vite?.close()
    await new Promise<void>((resolve, reject) => backend.close(error => error ? reject(error) : resolve()))
  }
})
