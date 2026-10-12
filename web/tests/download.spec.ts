import { expect, test } from '@playwright/test'

const defaults = {
  mode: 'video',
  quality: 'best',
  format: 'auto',
  destination: 'default',
  filename: null,
  subtitles: false,
  automatic_captions: false,
  subtitle_languages: ['en'],
  subtitle_format: 'best',
  embed_subtitles: false,
  embed_metadata: false,
  save_thumbnail: false,
  embed_thumbnail: false,
  embed_chapters: false,
  split_chapters: false,
  remux: 'auto',
  use_archive: false,
  playlist_start: 1,
  playlist_end: null,
  minimum_duration: null,
  maximum_duration: null,
  output_template: null,
  file_conflict: 'rename',
  retry_count: 3,
  rate_limit: null,
  fragment_concurrency: 1,
  proxy: null,
  http_headers: [],
  use_cookie_file: false,
  custom_options: [],
}
const item = (index: number) => ({
  id: String(index),
  url: `https://example.com/${index}`,
  title: `Video ${index}`,
  uploader: 'Uploader',
  thumbnail_url: null,
  duration_seconds: 60,
  playlist_index: index,
  formats: [
    {
      id: '1',
      extension: 'mp4',
      video_codec: 'h264',
      audio_codec: 'aac',
      width: 1280,
      height: 720,
      filesize_bytes: null,
    },
  ],
})

test.beforeEach(async ({ page }) => {
  await page.route('https://i.ytimg.com/**', (route) =>
    route.fulfill({
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="160" height="90"><rect width="160" height="90" fill="#cad7df"/></svg>',
    }),
  )
  await page.route('**/api/settings', (route) =>
    route.fulfill({
      json: {
        defaults,
        allowed_modes: ['video', 'audio'],
        allowed_qualities: ['best', '720p'],
        allowed_formats: ['auto', 'mp4', 'mp3'],
        destinations: ['default'],
        worker_count: 1,
        cookie_file_available: false,
      },
    }),
  )
  await page.route('**/api/jobs/events', (route) =>
    route.fulfill({ contentType: 'text/event-stream', body: 'event: jobs\ndata: {"jobs":[]}\n\n' }),
  )
  await page.route('**/api/preview', (route) =>
    route.fulfill({
      json: {
        source_url: 'https://www.youtube.com/playlist?list=PLtestPlaylist123',
        kind: 'playlist',
        title: 'My playlist',
        items: [item(1), item(2), item(3)],
        total_items: 3,
      },
    }),
  )
})

async function preview(page: import('@playwright/test').Page) {
  await page.goto('/')
  await page
    .getByLabel('Video link', { exact: true })
    .fill('https://www.youtube.com/playlist?list=PLtestPlaylist123')
  await page.getByRole('button', { name: 'Preview', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'My playlist' })).toBeVisible()
}

test('submits the selected playlist range and compatible audio settings once', async ({ page }) => {
  const submissions: unknown[] = []
  await page.route('**/api/jobs', async (route) => {
    const body = route.request().postDataJSON()
    submissions.push(body)
    await new Promise((resolve) => setTimeout(resolve, 150))
    await route.fulfill({
      status: 201,
      json: {
        id: 'job-1',
        source_url: body.url,
        title: 'My playlist',
        status: 'queued',
        selection: body.selection,
        settings: body.settings,
        progress: {
          percent: null,
          speed_bytes_per_second: null,
          eta_seconds: null,
          downloaded_bytes: 0,
          total_bytes: null,
        },
        output_name: null,
        error: null,
        created_at: '',
        updated_at: '',
      },
    })
  })
  await preview(page)
  await page
    .getByRole('combobox', { name: 'Playlist download selection', exact: true })
    .selectOption('range')
  await page.getByRole('spinbutton', { name: 'First playlist item', exact: true }).fill('2')
  await page.getByRole('spinbutton', { name: 'Last playlist item', exact: true }).fill('3')
  await page.getByLabel('Container', { exact: true }).selectOption('mp4')
  await page.getByRole('radio', { name: 'Audio' }).check()
  await expect(page.getByLabel('Audio format')).toHaveValue('auto')
  await expect(page.getByLabel('Audio format').locator('option[value="mp4"]')).toHaveCount(0)
  await page.getByLabel('Audio format').selectOption('mp3')
  await page.getByLabel('Choose my own file name').check()
  await page.getByLabel('New file name').fill('Custom name')
  await page.getByRole('button', { name: 'Add to downloads', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Adding…' })).toBeDisabled()
  await expect(page.getByText('Added to downloads.', { exact: true })).toBeVisible()
  expect(submissions).toEqual([
    {
      url: 'https://www.youtube.com/playlist?list=PLtestPlaylist123',
      selection: { item_indices: [2, 3] },
      settings: { ...defaults, mode: 'audio', format: 'mp3', filename: 'Custom name' },
    },
  ])
  await expect(page.getByText('QUEUED', { exact: true })).toBeVisible()
})

test('shows field validation errors and supports correction', async ({ page }) => {
  await page.route('**/api/jobs', (route) =>
    route.fulfill({
      status: 422,
      json: {
        error: {
          code: 'validation_error',
          message: 'Request validation failed',
          details: [
            {
              location: ['body', 'settings', 'filename'],
              message: 'Filename contains unsupported characters',
              code: 'value_error',
            },
          ],
        },
      },
    }),
  )
  await preview(page)
  await page.getByLabel('Choose my own file name').check()
  await page.getByLabel('New file name').fill('bad/name')
  await page.getByRole('button', { name: 'Add to downloads', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText(
    'settings › filename: Filename contains unsupported characters',
  )
  await page.getByLabel('New file name').fill('good-name')
  await expect(page.getByRole('alert')).toHaveCount(0)
  await page.getByLabel('Video link', { exact: true }).fill('https://youtu.be/dQw4w9WgXcQ')
  await expect(page.getByRole('button', { name: 'Add to downloads', exact: true })).toBeDisabled()
})

test('stacks controls without horizontal overflow on small screens', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await preview(page)
  await expect(page.getByLabel('Save location')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
  await page.screenshot({ path: '/tmp/vespertape-m4-mobile.png', fullPage: true })
})

test('disables invalid selections', async ({ page }) => {
  await preview(page)
  await page
    .getByRole('combobox', { name: 'Playlist download selection', exact: true })
    .selectOption('one')
  await page.getByRole('spinbutton', { name: 'First playlist item', exact: true }).fill('99')
  await expect(page.getByRole('button', { name: 'Add to downloads', exact: true })).toBeDisabled()
})

test('blocks previews with no downloadable formats', async ({ page }) => {
  await page.route('**/api/preview', (route) =>
    route.fulfill({
      json: {
        source_url: 'https://www.youtube.com/playlist?list=PLtestPlaylist123',
        kind: 'video',
        title: 'My playlist',
        items: [{ ...item(1), formats: [], playlist_index: null }],
        total_items: null,
      },
    }),
  )
  await preview(page)
  await expect(page.getByText('No downloadable formats are available for this item.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Add to downloads', exact: true })).toBeDisabled()
})

test('uses the reference window structure and opens the server folder chooser', async ({
  page,
}) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'What would you like to save?' })).toBeVisible()
  await expect(page.locator('.variant-a > .skin > .well')).toHaveCount(1)
  await expect(page.locator('.skin > .history-panel')).toBeVisible()
  await page.getByRole('button', { name: 'Choose folder', exact: true }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByRole('radio', { name: 'Downloads Default save folder' })).toBeChecked()
  await page.getByRole('button', { name: 'Use this folder', exact: true }).click()
  await expect(page.getByRole('dialog')).not.toBeVisible()
  await expect(page.getByLabel('Save location')).toHaveValue('Downloads')
  await page.getByText('More ways to customize', { exact: false }).click()
  await expect(page.getByRole('heading', { name: 'Subtitles & captions' })).toBeVisible()
  await expect(page.getByLabel('Download uploaded subtitles')).toBeEnabled()
  await expect(page.getByLabel('Use server cookie file')).toBeDisabled()
})

for (const url of [
  'https://example.com/watch?v=dQw4w9WgXcQ',
  'https://youtube.com.evil.example/watch?v=dQw4w9WgXcQ',
  'https://youtube.com/watch?v=short',
  'https://youtube.com/watch?v=dQw4w9WgXcQ%0A',
  'https://youtube.com/playlist?list=',
  'https://@youtube.com/watch?v=dQw4w9WgXcQ',
]) {
  test(`rejects invalid source before requesting preview: ${url}`, async ({ page }) => {
    let previewRequests = 0
    await page.route('**/api/preview', (route) => {
      previewRequests += 1
      return route.abort()
    })
    await page.goto('/')
    await page.getByLabel('Video link', { exact: true }).fill(url)
    await expect(page.getByRole('alert')).toContainText(/YouTube/)
    await expect(page.getByRole('button', { name: 'Preview', exact: true })).toBeDisabled()
    await expect(page.getByRole('button', { name: 'Add to downloads', exact: true })).toBeDisabled()
    expect(previewRequests).toBe(0)
    await page.getByLabel('Video link', { exact: true }).fill('https://youtu.be/dQw4w9WgXcQ')
    await expect(page.getByRole('alert')).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Preview', exact: true })).toBeEnabled()
  })
}

test('switches quality controls to audio and restores the chosen video resolution', async ({
  page,
}) => {
  await page.goto('/')
  await page.getByLabel('Resolution', { exact: true }).selectOption('720p')
  await page.getByLabel('Container', { exact: true }).selectOption('mp4')
  await page.getByRole('radio', { name: 'Audio', exact: true }).check()
  await expect(page.locator('.options-plate')).not.toContainText('720p')
  await expect(page.getByLabel('Audio quality', { exact: true })).toHaveValue('best')
  await expect(page.getByLabel('Audio quality', { exact: true })).toBeDisabled()
  await expect(page.getByLabel('Audio format', { exact: true })).toHaveValue('auto')
  await page.getByRole('radio', { name: 'Video', exact: true }).check()
  await expect(page.getByLabel('Resolution', { exact: true })).toHaveValue('720p')
  await expect(page.getByLabel('Audio quality', { exact: true })).toHaveCount(0)
})

test('shows thumbnail lists without Save links and supports pause/resume', async ({ page }) => {
  let job = {
    id: 'active',
    thumbnail_url: 'https://i.ytimg.com/vi/n7Hi2k6aHBw/hqdefault.jpg',
    title: 'Active video',
    status: 'downloading',
    settings: defaults,
    progress: { percent: 42, speed_bytes_per_second: 1048576, eta_seconds: 9 },
    output_name: null,
    error: null,
  }
  const saved = {
    ...job,
    id: 'saved',
    title: 'Saved playlist',
    status: 'complete',
    output_folder: 'Saved playlist',
    output_files: ['one.mp4', 'two.mp4'],
    downloaded_items: [
      {
        filename: 'one.mp4',
        title: 'First video',
        thumbnail_url: 'https://i.ytimg.com/vi/n7Hi2k6aHBw/hqdefault.jpg',
      },
      {
        filename: 'two.mp4',
        title: 'Second video',
        thumbnail_url: 'https://i.ytimg.com/vi/YoiPvImmyyQ/hqdefault.jpg',
      },
    ],
  }
  await page.route('**/api/jobs/events', (route) =>
    route.fulfill({
      contentType: 'text/event-stream',
      body: `event: jobs\ndata: ${JSON.stringify({ jobs: [job, saved] })}\n\n`,
    }),
  )
  await page.route('**/api/jobs', (route) => route.fulfill({ json: { jobs: [job, saved] } }))
  await page.route('**/api/jobs/active/actions', async (route) => {
    const { action } = route.request().postDataJSON()
    job = { ...job, status: action === 'pause' ? 'paused' : 'queued' }
    await route.fulfill({ json: job })
  })
  await page.goto('/')
  const active = page.locator('article').filter({ hasText: 'Active video' })
  await expect(active).toContainText('42.0%')
  await expect(active).toContainText('1.00 MB/s')
  await active.getByRole('button', { name: 'Pause', exact: true }).click()
  await expect(active).toContainText('PAUSED')
  await active.getByRole('button', { name: 'Resume', exact: true }).click()
  await expect(active).toContainText('QUEUED')
  const history = page.locator('article').filter({ hasText: 'Saved playlist' })
  await expect(history.getByRole('link')).toHaveCount(0)
  await expect(history.locator('.saved-items li')).toHaveCount(2)
  await expect(history.getByRole('img', { name: 'Thumbnail for First video' })).toBeVisible()
  await expect(history).toContainText('Downloads/Saved playlist')
  await expect(active.getByRole('img', { name: 'Thumbnail for Active video' })).toBeVisible()
  const dimensions = await active.locator('.download-thumbnail').boundingBox()
  expect(dimensions!.width / dimensions!.height).toBeCloseTo(16 / 9, 1)
  await page.setViewportSize({ width: 375, height: 812 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
})

test('submits advanced settings and keeps them after API validation errors', async ({ page }) => {
  let submitted: any
  await page.route('**/api/jobs', (route) => {
    submitted = route.request().postDataJSON()
    return route.fulfill({
      status: 422,
      json: { error: { code: 'validation_error', message: 'Invalid option', details: [] } },
    })
  })
  await preview(page)
  await page.getByText('More ways to customize', { exact: false }).click()
  await page.getByLabel('Download uploaded subtitles').check()
  await page.getByLabel('Subtitle languages', { exact: true }).fill('en, fr')
  await page.getByLabel('Subtitle format', { exact: true }).selectOption('srt')
  await page.getByLabel('Retries', { exact: true }).fill('5')
  await page.getByLabel('Rate limit (bytes per second)', { exact: true }).fill('1048576')
  await page.getByLabel('Additional HTTP headers').fill('Accept-Language: en')
  await page.getByLabel('--prefer-free-formats', { exact: true }).check()
  await page.getByRole('button', { name: 'Add to downloads', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Invalid option')
  expect(submitted.settings).toMatchObject({
    subtitles: true,
    subtitle_languages: ['en', 'fr'],
    subtitle_format: 'srt',
    retry_count: 5,
    rate_limit: 1048576,
    http_headers: ['Accept-Language: en'],
    custom_options: ['--prefer-free-formats'],
  })
  await expect(page.getByLabel('Download uploaded subtitles')).toBeChecked()
  await page.setViewportSize({ width: 375, height: 812 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
  await page.screenshot({ path: '/tmp/vespertape-m6-mobile.png', fullPage: true })
})

test('cancels queued work, retries failures, and removes canceled history', async ({ page }) => {
  const makeJob = (id: string, status: string) => ({
    id,
    title: `${id} video`,
    status,
    settings: defaults,
    updated_at: '2026-10-07T00:00:00Z',
    progress: { percent: null, speed_bytes_per_second: null, eta_seconds: null },
    output_name: null,
    error: status === 'failed' ? { code: 'download_failed', message: 'Source unavailable' } : null,
  })
  let jobs = [makeJob('waiting', 'queued'), makeJob('broken', 'failed')]
  const actions: unknown[] = []
  await page.route('**/api/jobs/events', (route) =>
    route.fulfill({
      contentType: 'text/event-stream',
      body: `event: jobs\ndata: ${JSON.stringify({ jobs })}\n\n`,
    }),
  )
  await page.route('**/api/jobs', (route) => route.fulfill({ json: { jobs } }))
  await page.route('**/api/jobs/*/actions', (route) => {
    const id = route.request().url().split('/').at(-2)!
    const { action } = route.request().postDataJSON()
    actions.push({ id, action })
    jobs = jobs.map((job) =>
      job.id === id ? makeJob(id, action === 'cancel' ? 'canceled' : 'queued') : job,
    )
    return route.fulfill({ json: jobs.find((job) => job.id === id) })
  })
  await page.route('**/api/jobs/waiting', (route) => {
    expect(route.request().method()).toBe('DELETE')
    jobs = jobs.filter((job) => job.id !== 'waiting')
    return route.fulfill({ status: 204 })
  })
  await page.goto('/')
  const waiting = page.locator('article').filter({ hasText: 'waiting video' })
  const broken = page.locator('article').filter({ hasText: 'broken video' })
  await expect(broken).toContainText('Source unavailable')
  await waiting.getByRole('button', { name: 'Cancel', exact: true }).click()
  await expect(waiting).toContainText('CANCELED')
  await broken.getByRole('button', { name: 'Retry', exact: true }).click()
  await expect(broken).toContainText('QUEUED')
  await expect(broken).not.toContainText('Source unavailable')
  await waiting.getByRole('button', { name: 'Remove', exact: true }).click()
  await expect(waiting).toHaveCount(0)
  expect(actions).toEqual([
    { id: 'waiting', action: 'cancel' },
    { id: 'broken', action: 'retry' },
  ])
})

test('allows flat playlist selection and explains deferred format checks', async ({ page }) => {
  await page.route('**/api/preview', (route) =>
    route.fulfill({
      json: {
        source_url: 'https://www.youtube.com/playlist?list=PLtestPlaylist123',
        kind: 'playlist',
        title: 'My playlist',
        total_items: 51,
        items: [1, 2, 3].map((index) => ({ ...item(index), formats: [], formats_checked: false })),
      },
    }),
  )
  await preview(page)
  await expect(
    page.getByText('Playlist listed. Availability and formats are checked when downloading.'),
  ).toBeVisible()
  await expect(page.getByRole('button', { name: 'Add to downloads', exact: true })).toBeEnabled()
  await page
    .getByRole('combobox', { name: 'Playlist download selection', exact: true })
    .selectOption('one')
  await page.getByRole('spinbutton', { name: 'First playlist item', exact: true }).fill('2')
  await expect(page.getByRole('button', { name: 'Add to downloads', exact: true })).toBeEnabled()
})

test('shows a timeout instead of leaving preview loading indefinitely', async ({ page }) => {
  await page.clock.install()
  await page.route('**/api/preview', () => {})
  await page.goto('/')
  await page.getByLabel('Video link', { exact: true }).fill('https://youtu.be/dQw4w9WgXcQ')
  await page.getByRole('button', { name: 'Preview', exact: true }).click()
  await page.clock.fastForward(30001)
  await expect(page.getByRole('alert')).toContainText('Preview took too long')
  await expect(page.getByRole('button', { name: 'Preview', exact: true })).toBeEnabled()
})

test('confirming or canceling the folder dialog does not submit a ready download', async ({
  page,
}) => {
  let submissions = 0
  await page.route('**/api/jobs', (route) => {
    submissions += 1
    return route.fulfill({
      status: 500,
      json: {
        error: { code: 'unexpected_submission', message: 'Unexpected submission', details: [] },
      },
    })
  })
  await preview(page)
  await expect(page.getByRole('button', { name: 'Add to downloads', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: 'Choose folder', exact: true }).click()
  await page.getByRole('button', { name: 'Use this folder', exact: true }).click()
  await expect(page.getByRole('dialog')).not.toBeVisible()
  await page.getByRole('button', { name: 'Choose folder', exact: true }).click()
  await page.getByRole('button', { name: 'Keep current', exact: true }).click()
  await expect(page.getByRole('dialog')).not.toBeVisible()
  await expect(page.getByRole('button', { name: 'Add to downloads', exact: true })).toBeEnabled()
  expect(submissions).toBe(0)
})
