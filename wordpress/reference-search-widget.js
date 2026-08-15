(() => {
  const root = document.querySelector('[data-thc-reference-tool]')
  if (!root) return

  const indexUrl = root.dataset.indexUrl || '/reference-image-index.json'
  const queryEl = root.querySelector('input[name="q"]')
  const resultsEl = root.querySelector('[data-results]')
  const summaryEl = root.querySelector('[data-summary]')

  const escapeHtml = (value = '') => value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')

  const renderSummary = (images = []) => {
    if (!summaryEl) return
    const total = images.length
    const score = Math.min(100, Math.max(20, Math.round((total / 12) * 100)))
    const status = total >= 12 ? 'Benchmark-ready reference set' : total >= 6 ? 'Improving reference coverage' : 'Reference coverage needs more images'
    summaryEl.innerHTML = `
      <div class="thc-reference-summary-card">
        <span>Reference evidence</span>
        <strong>${score}%</strong>
        <small>${status}</small>
        <em>${total} indexed media records</em>
      </div>
    `
  }

  const render = (items) => {
    if (!resultsEl) return
    if (!items.length) {
      resultsEl.innerHTML = '<p class="thc-reference-empty">No approved reference images match your search yet.</p>'
      return
    }

    resultsEl.innerHTML = items.map((item) => `
      <article class="thc-reference-result">
        <strong>${escapeHtml(item.datasetId || 'Dataset image')}</strong>
        <p>${escapeHtml(item.filename || item.path)}</p>
        <small>${escapeHtml(item.path)}</small>
      </article>
    `).join('')
  }

  async function search(query) {
    try {
      const response = await fetch(indexUrl)
      if (!response.ok) throw new Error('Index load failed')
      const payload = await response.json()
      const images = Array.isArray(payload.images) ? payload.images : []
      renderSummary(images)
      const clean = query.trim().toLowerCase()
      const filtered = !clean
        ? images.slice(0, 8)
        : images.filter((item) => {
            const haystack = [
              item.datasetId,
              item.filename,
              item.folder,
              item.path,
              item.searchText,
              item.sha256,
              ...(item.labels || []),
            ].join(' ').toLowerCase()
            return haystack.includes(clean)
          }).slice(0, 8)

      render(filtered)
    } catch (error) {
      if (summaryEl) {
        summaryEl.innerHTML = '<div class="thc-reference-summary-card"><span>Reference evidence</span><strong>0%</strong><small>Reference index unavailable</small></div>'
      }
      resultsEl.innerHTML = '<p class="thc-reference-empty">Reference index unavailable. Please confirm the dataset index is published.</p>'
    }
  }

  queryEl?.addEventListener('input', (event) => {
    search(event.target.value)
  })

  search('')
})()
