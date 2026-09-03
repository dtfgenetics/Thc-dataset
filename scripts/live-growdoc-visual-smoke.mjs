#!/usr/bin/env node

import { execFileSync, spawn } from 'node:child_process'
import { mkdir, mkdtemp, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const siteUrl = process.env.GROW_DOC_URL || 'https://dtfseeds.com/thc-grow-doc/'
const outputDir = process.env.GROW_DOC_QA_DIR || 'qa-output'
const port = 9300 + Math.floor(Math.random() * 500)

function resolveChrome() {
  if (process.env.CHROME_BIN) return process.env.CHROME_BIN
  for (const candidate of ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser']) {
    try {
      return execFileSync('which', [candidate], { encoding: 'utf8' }).trim()
    } catch {
      // Try the next browser name.
    }
  }
  throw new Error('Chrome/Chromium was not found on the runner.')
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

async function waitForJson(url, timeoutMs = 15_000) {
  const deadline = Date.now() + timeoutMs
  let lastError
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url)
      if (response.ok) return await response.json()
      lastError = new Error(`${response.status} ${response.statusText}`)
    } catch (error) {
      lastError = error
    }
    await sleep(200)
  }
  throw new Error(`Timed out waiting for ${url}: ${lastError?.message || 'unknown error'}`)
}

function makeCdpClient(webSocketUrl) {
  const socket = new WebSocket(webSocketUrl)
  const pending = new Map()
  let nextId = 1

  socket.addEventListener('message', (event) => {
    const message = JSON.parse(String(event.data))
    if (!message.id) return
    const waiter = pending.get(message.id)
    if (!waiter) return
    pending.delete(message.id)
    if (message.error) waiter.reject(new Error(`${message.error.code}: ${message.error.message}`))
    else waiter.resolve(message.result)
  })

  const ready = new Promise((resolve, reject) => {
    socket.addEventListener('open', resolve, { once: true })
    socket.addEventListener('error', () => reject(new Error('Chrome DevTools websocket failed to open.')), { once: true })
  })

  return {
    async send(method, params = {}) {
      await ready
      const id = nextId++
      const promise = new Promise((resolve, reject) => pending.set(id, { resolve, reject }))
      socket.send(JSON.stringify({ id, method, params }))
      return promise
    },
    close() {
      socket.close()
    },
  }
}

async function evaluate(client, expression) {
  const result = await client.send('Runtime.evaluate', {
    expression,
    returnByValue: true,
    awaitPromise: true,
  })
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text || 'Runtime evaluation failed.')
  return result.result?.value
}

async function waitFor(client, expression, label, timeoutMs = 15_000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    if (await evaluate(client, expression)) return
    await sleep(200)
  }
  throw new Error(`Timed out waiting for ${label}.`)
}

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

function assertDark(color, label) {
  const normalized = String(color || '').replaceAll(' ', '').toLowerCase()
  assert(normalized && normalized !== 'rgb(255,255,255)' && normalized !== 'rgba(255,255,255,1)', `${label} regressed to white (${color}).`)
}

async function capture(client, name) {
  const screenshot = await client.send('Page.captureScreenshot', {
    format: 'png',
    fromSurface: true,
    captureBeyondViewport: false,
  })
  await writeFile(join(outputDir, `${name}.png`), Buffer.from(screenshot.data, 'base64'))
}

async function loadViewport(client, { name, width, height }) {
  await client.send('Emulation.setDeviceMetricsOverride', {
    width,
    height,
    deviceScaleFactor: 1,
    mobile: false,
    screenWidth: width,
    screenHeight: height,
  })
  const url = new URL(siteUrl)
  url.searchParams.set('growdoc_visual_qa', `${Date.now()}-${name}`)
  await client.send('Page.navigate', { url: url.toString() })
  await waitFor(client, "Boolean(document.querySelector('.app-shell'))", 'React app mount')
  await waitFor(client, "document.fonts ? document.fonts.status === 'loaded' : true", 'web fonts', 10_000)
  await sleep(350)

  const report = await evaluate(client, `(() => {
    const hero = document.querySelector('.grow-doc-hero');
    const resultPanel = document.querySelector('.result-panel');
    const evidenceGrid = document.querySelector('.evidence-grid');
    const desktopNav = document.querySelector('.desktop-nav');
    const menuButton = document.querySelector('.menu-button');
    const heading = hero?.querySelector('h1');
    const bodyStyle = getComputedStyle(document.body);
    const heroStyle = hero ? getComputedStyle(hero) : null;
    const resultStyle = resultPanel ? getComputedStyle(resultPanel) : null;
    const gridStyle = evidenceGrid ? getComputedStyle(evidenceGrid) : null;
    const headingStyle = heading ? getComputedStyle(heading) : null;
    return {
      width: innerWidth,
      height: innerHeight,
      appMounted: Boolean(document.querySelector('.app-shell')),
      heading: heading?.textContent?.trim() || '',
      bodyBackground: bodyStyle.backgroundColor,
      bodyBackgroundImage: bodyStyle.backgroundImage,
      heroBackground: heroStyle?.backgroundImage || '',
      heroRadius: parseFloat(heroStyle?.borderRadius || '0'),
      resultBackground: resultStyle?.backgroundColor || '',
      evidenceColumns: gridStyle?.gridTemplateColumns?.split(/\\s+/).filter(Boolean).length || 0,
      desktopNavDisplay: desktopNav ? getComputedStyle(desktopNav).display : 'missing',
      menuDisplay: menuButton ? getComputedStyle(menuButton).display : 'missing',
      headingFontSize: parseFloat(headingStyle?.fontSize || '0'),
      overflowX: document.documentElement.scrollWidth - innerWidth,
    };
  })()`)

  assert(report.appMounted, `${name}: React app did not mount.`)
  assert(report.heading === 'Document the plant before you diagnose it.', `${name}: unexpected hero heading: ${report.heading}`)
  assertDark(report.bodyBackground, `${name}: body`)
  assertDark(report.resultBackground, `${name}: result panel`)
  assert(report.heroBackground.includes('gradient'), `${name}: hero lost its designed gradient treatment.`)
  assert(report.heroRadius >= 12, `${name}: hero radius is unexpectedly small (${report.heroRadius}).`)
  assert(report.overflowX <= 1, `${name}: horizontal overflow detected (${report.overflowX}px).`)

  if (width >= 900) {
    assert(report.desktopNavDisplay !== 'none', `${name}: desktop navigation is hidden.`)
    assert(report.menuDisplay === 'none', `${name}: mobile menu button is visible on desktop.`)
    assert(report.evidenceColumns >= 4, `${name}: evidence grid collapsed unexpectedly (${report.evidenceColumns} columns).`)
    assert(report.headingFontSize >= 40, `${name}: hero heading is too small (${report.headingFontSize}px).`)
  } else {
    assert(report.desktopNavDisplay === 'none', `${name}: desktop navigation is visible on mobile.`)
    assert(report.menuDisplay !== 'none', `${name}: mobile menu button is hidden.`)
    assert(report.evidenceColumns === 2, `${name}: mobile evidence grid should have 2 columns, found ${report.evidenceColumns}.`)
    assert(report.headingFontSize >= 32 && report.headingFontSize <= 48, `${name}: mobile heading size is out of range (${report.headingFontSize}px).`)
  }

  await capture(client, name)
  return report
}

async function inspectAtlas(client) {
  const switched = await evaluate(client, `(() => {
    const button = [...document.querySelectorAll('.desktop-nav button')].find((item) => item.textContent?.trim() === 'Plant atlas');
    if (!button) return false;
    button.click();
    return true;
  })()`)
  assert(switched, 'Could not switch to Plant atlas from desktop navigation.')
  await waitFor(client, "Boolean(document.querySelector('.atlas-workspace-v2'))", 'Plant atlas workspace')
  await sleep(250)
  const atlas = await evaluate(client, `(() => {
    const workspace = document.querySelector('.atlas-workspace-v2');
    const rail = document.querySelector('.atlas-section-rail');
    return {
      workspaceBackground: workspace ? getComputedStyle(workspace).backgroundColor : '',
      railBackground: rail ? getComputedStyle(rail).backgroundColor : '',
      overflowX: document.documentElement.scrollWidth - innerWidth,
    };
  })()`)
  assertDark(atlas.workspaceBackground, 'atlas workspace')
  assertDark(atlas.railBackground, 'atlas rail')
  assert(atlas.overflowX <= 1, `Atlas horizontal overflow detected (${atlas.overflowX}px).`)
  await capture(client, 'atlas-desktop')
  return atlas
}

async function run() {
  await mkdir(outputDir, { recursive: true })
  const chrome = resolveChrome()
  const profile = await mkdtemp(join(tmpdir(), 'growdoc-chrome-'))
  const chromeProcess = spawn(chrome, [
    '--headless=new',
    '--no-sandbox',
    '--disable-gpu',
    '--hide-scrollbars',
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${profile}`,
    'about:blank',
  ], { stdio: ['ignore', 'pipe', 'pipe'] })

  let stderr = ''
  chromeProcess.stderr.on('data', (chunk) => { stderr += String(chunk) })

  let client
  try {
    const pages = await waitForJson(`http://127.0.0.1:${port}/json/list`)
    const page = pages.find((item) => item.type === 'page')
    if (!page?.webSocketDebuggerUrl) throw new Error('Chrome did not expose a debuggable page.')
    client = makeCdpClient(page.webSocketDebuggerUrl)
    await client.send('Page.enable')
    await client.send('Runtime.enable')

    const desktop = await loadViewport(client, { name: 'diagnose-desktop', width: 1440, height: 1100 })
    const atlas = await inspectAtlas(client)
    const mobile = await loadViewport(client, { name: 'diagnose-mobile', width: 390, height: 844 })

    const menuOpened = await evaluate(client, `(() => {
      const button = document.querySelector('.menu-button');
      if (!button) return false;
      button.click();
      return Boolean(document.querySelector('.mobile-nav'));
    })()`)
    assert(menuOpened, 'Mobile navigation did not open.')
    const mobileMenuOverflow = await evaluate(client, "document.documentElement.scrollWidth - innerWidth")
    assert(mobileMenuOverflow <= 1, `Mobile menu introduced horizontal overflow (${mobileMenuOverflow}px).`)
    await capture(client, 'mobile-menu')

    const summary = { ok: true, url: siteUrl, desktop, atlas, mobile, mobileMenuOverflow }
    await writeFile(join(outputDir, 'visual-smoke.json'), JSON.stringify(summary, null, 2) + '\n')
    console.log(JSON.stringify(summary, null, 2))
  } finally {
    client?.close()
    chromeProcess.kill('SIGTERM')
    await sleep(150)
    if (!chromeProcess.killed) chromeProcess.kill('SIGKILL')
  }

  if (stderr && process.env.GROW_DOC_QA_DEBUG === '1') process.stderr.write(stderr)
}

run().catch((error) => {
  console.error(error.stack || error.message)
  process.exitCode = 1
})
