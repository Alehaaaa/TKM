(function () {
  const releasesUrl = new URL('releases.json', document.baseURI);
  let releasesPromise;
  let releaseObserver;

  // ---------------------------------------------------------------------
  // URL helpers
  // ---------------------------------------------------------------------

  // Returns the actual filename ("about.html", "index.html", ...) for a
  // given URL, whether or not the URL already has a .html extension.
  function normalizePage(url) {
    const parsed = new URL(url, window.location.href);
    const last = parsed.pathname.replace(/\/+$/, '').split('/').pop() || '';
    if (last.endsWith('.html')) return last;
    return ['about', 'changelog', 'help'].includes(last) ? `${last}.html` : 'index.html';
  }

  function setActiveNav(url) {
    const current = normalizePage(url);
    document.querySelectorAll('.button-container a').forEach((link) => {
      const isActive = normalizePage(link.href) === current;
      if (isActive) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    });
  }

  // ---------------------------------------------------------------------
  // Release data rendering
  // ---------------------------------------------------------------------

  function releaseText(text) {
    return String(text || '').trim();
  }

  function sentence(text) {
    const value = releaseText(text);
    return value && /[.!?]$/.test(value) ? value : `${value}.`;
  }

  function publishedLabel(release) {
    const label = releaseText(release && release.publishedLabel);
    return label && label !== 'Release date pending' ? `Published ${label}` : 'Release date pending';
  }

  function getReleaseData() {
    if (!releasesPromise) {
      releasesPromise = fetch(releasesUrl, { cache: 'no-cache' })
        .then((response) => {
          if (!response.ok) {
            throw new Error(`Release data failed with ${response.status}`);
          }
          return response.json();
        });
    }
    return releasesPromise;
  }

  function renderLatestRelease(release) {
    const panel = document.querySelector('.download-panel');
    if (!panel || !release) {
      return;
    }

    const title = panel.querySelector('#latest-download');
    const summary = panel.querySelector('p:last-child');
    const download = panel.querySelector('.primary-button');

    if (title) {
      title.textContent = release.version;
    }
    if (summary) {
      summary.textContent = `${publishedLabel(release)}. Supports Maya 2022 through 2027 on Windows, Linux and macOS.`;
    }
    if (download && release.downloadUrl) {
      download.href = release.downloadUrl;
      download.textContent = `Download latest · ${release.version}`;
    }
    const changelog = panel.querySelector('.secondary-link');
    if (changelog) changelog.href = 'changelog/';
  }

  function renderReleaseCard(release) {
    const article = document.createElement('article');
    article.className = 'release-card';
    article.id = `release-${release.version.replace(/\./g, '-')}`;

    const heading = document.createElement('h2');
    const titleLink = document.createElement('a');
    titleLink.href = release.downloadUrl || release.url;
    titleLink.textContent = release.version;
    heading.append(titleLink);

    const date = document.createElement('p');
    date.className = 'release-date';
    date.textContent = publishedLabel(release);

    const list = document.createElement('ul');
    const entries = Array.isArray(release.entries) ? release.entries : [];
    if (entries.length) {
      entries.forEach((entry) => {
        const item = document.createElement('li');
        const label = document.createElement('strong');
        label.textContent = `${releaseText(entry.label || entry.kind || 'Changed')}:`;
        item.append(label, ` ${sentence(entry.description)}`);
        list.append(item);
      });
    } else {
      const item = document.createElement('li');
      item.textContent = 'No changelog entries recorded for this version.';
      list.append(item);
    }

    article.append(heading, date, list);
    if (release.compareUrl) {
      const compare = document.createElement('a');
      compare.className = 'release-compare';
      compare.href = release.compareUrl;
      compare.target = '_blank';
      compare.rel = 'noopener';
      compare.textContent = 'Full changelog';
      article.append(compare);
    }

    return article;
  }

  function renderReleaseList(releases) {
    const list = document.querySelector('.release-list');
    if (!list || !Array.isArray(releases) || !releases.length) {
      return;
    }

    list.replaceChildren(...releases.map(renderReleaseCard));
  }

  function hydrateReleaseData() {
    return getReleaseData()
      .then((data) => {
        const releases = Array.isArray(data.releases) ? data.releases : [];
        renderLatestRelease(releases[0]);
        renderReleaseList(releases);
      })
      .catch(() => {
        releasesPromise = null;
      });
  }

  // ---------------------------------------------------------------------
  // Smart helpers
  // ---------------------------------------------------------------------

  function detectedPlatform() {
    const platform = (navigator.userAgentData && navigator.userAgentData.platform) || navigator.platform || '';
    if (/mac/i.test(platform)) return 'macOS';
    if (/win/i.test(platform)) return 'Windows';
    if (/linux/i.test(platform)) return 'Linux';
    return 'Other';
  }

  function initPlatformDownload() {
    if (!document.querySelector('.download-actions')) return;
    const platform = detectedPlatform();
    let note = document.querySelector('[data-platform-note]');
    if (!note) {
      note = document.createElement('span');
      note.className = 'download-context';
      note.dataset.platformNote = '';
      document.querySelector('.download-actions .primary-button')?.after(note);
    }
    note.textContent = platform === 'Other' ? 'Universal package · ZIP' : `Compatible with ${platform} · ZIP`;
  }

  function initVersionNavigator() {
    const list = document.querySelector('.release-list');
    const cards = [...document.querySelectorAll('.release-card')];
    if (!list || !cards.length || list.closest('.release-layout')) return;

    const layout = document.createElement('div');
    layout.className = 'release-layout';
    list.before(layout);

    const aside = document.createElement('aside');
    aside.className = 'version-navigator';
    aside.setAttribute('aria-label', 'Jump to a release');
    const heading = document.createElement('strong');
    heading.textContent = 'Jump to';
    const links = document.createElement('div');
    links.className = 'version-links';

    cards.forEach((card, index) => {
      const version = card.querySelector('h2')?.textContent.trim();
      if (!version) return;
      const link = document.createElement('a');
      link.href = `${window.location.pathname}#${card.id}`;
      link.textContent = version;
      link.classList.toggle('is-active', index === 0);
      link.addEventListener('click', (event) => {
        event.preventDefault();
        window.history.replaceState({}, '', link.href);
        card.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
      links.append(link);
    });

    aside.append(heading, links);
    layout.append(aside, list);

    if (releaseObserver) releaseObserver.disconnect();
    if ('IntersectionObserver' in window) {
      releaseObserver = new IntersectionObserver((entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (!visible) return;
        links.querySelectorAll('a').forEach((link) => {
          const active = link.hash === `#${visible.target.id}`;
          link.classList.toggle('is-active', active);
          if (active) link.scrollIntoView({ block: 'nearest', inline: 'nearest' });
        });
      }, { rootMargin: '-15% 0px -70% 0px', threshold: [0, 0.25, 0.6] });
      cards.forEach((card) => releaseObserver.observe(card));
    }
  }

  function searchItems(releases) {
    const pages = [
      { title: 'Home', eyebrow: 'Page', description: 'Latest download and tool highlights', href: './' },
      { title: 'Install TheKeyMachine', eyebrow: 'Help', description: 'Personal installation, studio setup and updates', href: 'help/' },
      { title: 'Troubleshooting', eyebrow: 'Help', description: 'Installation, GitHub issues and community support', href: 'help/' },
      { title: 'Featured tools', eyebrow: 'Home', description: 'Nudge, Tracer, Temp Pivot and Animation Offset demonstrations', href: './#featured-tools' },
      { title: 'About TheKeyMachine', eyebrow: 'Page', description: 'Project, license, tools and supported platforms', href: 'about/' },
      { title: 'Release history', eyebrow: 'Changelog', description: 'Browse every feature, improvement and bug fix', href: 'changelog/' }
    ];
    const versions = releases.map((release) => ({
      title: `Version ${release.version}`,
      eyebrow: 'Release',
      description: (release.entries || []).map((entry) => entry.description).join(' · '),
      href: `changelog/#release-${release.version.replace(/\./g, '-')}`
    }));
    return pages.concat(versions);
  }

  function ensureSearchDialog() {
    if (document.querySelector('[data-site-search]')) return;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'site-search-button';
    button.dataset.searchOpen = '';
    button.setAttribute('aria-label', 'Search this site');
    button.innerHTML = '<svg class="search-icon" aria-hidden="true" viewBox="0 0 24 24"><circle cx="11" cy="11" r="6.5"></circle><path d="m16 16 4.25 4.25"></path></svg><span>Search</span><kbd>⌘ K</kbd>';
    document.querySelector('.button-container')?.append(button);

    const dialog = document.createElement('dialog');
    dialog.className = 'site-search-dialog';
    dialog.dataset.siteSearch = '';
    dialog.innerHTML = `
      <div class="search-dialog-header">
        <label for="site-search-input">Search TheKeyMachine</label>
        <button type="button" data-search-close aria-label="Close search">×</button>
      </div>
      <input id="site-search-input" type="search" placeholder="Search tools, fixes, help and releases…" autocomplete="off" data-site-search-input>
      <div class="site-search-results" data-site-search-results aria-live="polite"></div>
      <p class="search-hint">Press <kbd>Esc</kbd> to close</p>`;
    document.body.append(dialog);
  }

  async function runSiteSearch(query) {
    const results = document.querySelector('[data-site-search-results]');
    if (!results) return;
    const terms = query.toLowerCase().trim().split(/\s+/).filter(Boolean);
    if (!terms.length) {
      results.innerHTML = '<p class="search-empty">Try a tool name like “tracer” or a topic like “install”.</p>';
      return;
    }
    try {
      const data = await getReleaseData();
      const matches = searchItems(data.releases || []).filter((item) => {
        const haystack = `${item.title} ${item.eyebrow} ${item.description}`.toLowerCase();
        return terms.every((term) => haystack.includes(term));
      }).slice(0, 8);
      results.replaceChildren(...matches.map((item) => {
        const link = document.createElement('a');
        link.href = item.href;
        link.className = 'search-result';
        const eyebrow = document.createElement('span');
        eyebrow.textContent = item.eyebrow;
        const title = document.createElement('strong');
        title.textContent = item.title;
        const description = document.createElement('small');
        description.textContent = item.description;
        link.append(eyebrow, title, description);
        return link;
      }));
      if (!matches.length) results.innerHTML = '<p class="search-empty">No exact matches. Try fewer or broader words.</p>';
    } catch (_) {
      results.innerHTML = '<p class="search-empty">Search is temporarily unavailable.</p>';
    }
  }

  function handleHashTarget() {
    if (!window.location.hash) return false;
    const target = document.querySelector(window.location.hash);
    if (!target) return false;
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    target.classList.add('is-targeted');
    window.setTimeout(() => target.classList.remove('is-targeted'), 1800);
    return true;
  }

  function initPageFeatures() {
    initPlatformDownload();
    initVersionNavigator();
  }

  document.addEventListener('click', (event) => {
    if (event.target.matches('[data-site-search]')) {
      event.target.close();
      return;
    }
    if (event.target.closest('[data-search-open]')) {
      const dialog = document.querySelector('[data-site-search]');
      dialog?.showModal();
      dialog?.querySelector('[data-site-search-input]')?.focus();
      return;
    }
    if (event.target.closest('[data-search-close]')) {
      document.querySelector('[data-site-search]')?.close();
      return;
    }
  });

  document.addEventListener('input', (event) => {
    if (event.target.matches('[data-site-search-input]')) runSiteSearch(event.target.value);
  });

  document.addEventListener('keydown', (event) => {
    const isShortcut = (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k';
    if (!isShortcut) return;
    event.preventDefault();
    document.querySelector('[data-search-open]')?.click();
  });

  // ---------------------------------------------------------------------
  // Init
  // ---------------------------------------------------------------------

  setActiveNav(window.location.href);
  ensureSearchDialog();
  hydrateReleaseData().then(() => {
    initPageFeatures();
    handleHashTarget();
  });
})();
