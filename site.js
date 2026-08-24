(function () {
  const pageSelector = 'a[href$=".html"]';
  let releasesPromise;

  // ---------------------------------------------------------------------
  // URL helpers
  // ---------------------------------------------------------------------

  // Returns the actual filename ("about.html", "index.html", ...) for a
  // given URL, whether or not the URL already has a .html extension.
  function normalizePage(url) {
    const parsed = new URL(url, window.location.href);
    let file = parsed.pathname.split('/').pop() || 'index.html';
    if (file === '') file = 'index.html';
    if (!file.endsWith('.html')) file += '.html';
    return file;
  }

  // Given any URL (clean or with .html), returns the URL that should
  // actually be fetched from the server (always ends in .html).
  function toFetchUrl(url) {
    const parsed = new URL(url, window.location.href);
    if (!parsed.pathname.endsWith('.html')) {
      const segments = parsed.pathname.split('/');
      const last = segments[segments.length - 1];
      segments[segments.length - 1] = (last || 'index') + '.html';
      parsed.pathname = segments.join('/');
    }
    return parsed.toString();
  }

  // Given a URL (typically one that ends in .html), returns the "pretty"
  // URL without the extension, for use with history.pushState.
  function toCleanUrl(url) {
    const parsed = new URL(url, window.location.href);
    parsed.pathname = parsed.pathname
      .replace(/(^|\/)index\.html$/, '$1')
      .replace(/\.html$/, '');
    return parsed.toString();
  }

  function setActiveNav(url) {
    const current = normalizePage(url);
    document.querySelectorAll('.button-container a').forEach((link) => {
      const isActive = normalizePage(link.href) === current;
      link.toggleAttribute('aria-current', isActive);
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
      releasesPromise = fetch('releases.json', { cache: 'no-cache' })
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
    }
  }

  function renderReleaseCard(release) {
    const article = document.createElement('article');
    article.className = 'release-card';

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
    getReleaseData()
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
  // Client-side navigation
  // ---------------------------------------------------------------------

  function shouldHandle(link, event) {
    if (!link || event.defaultPrevented) {
      return false;
    }

    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) {
      return false;
    }

    if (link.target && link.target !== '_self') {
      return false;
    }

    const url = new URL(link.href, window.location.href);
    return url.origin === window.location.origin && url.pathname.endsWith('.html');
  }

  async function loadPage(url, pushState) {
    const fetchUrl = toFetchUrl(url);
    const response = await fetch(fetchUrl, { headers: { 'X-Requested-With': 'fetch' } });

    if (!response.ok) {
      window.location.href = url;
      return;
    }

    const html = await response.text();
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const nextMain = doc.querySelector('main');
    const currentMain = document.querySelector('main');

    if (!nextMain || !currentMain) {
      window.location.href = url;
      return;
    }

    document.title = doc.title;
    currentMain.replaceWith(nextMain);

    if (pushState) {
      window.history.pushState({}, doc.title, toCleanUrl(fetchUrl));
    }

    setActiveNav(fetchUrl);
    hydrateReleaseData();
    window.scrollTo({ top: 0, behavior: 'smooth' });

    const heading = document.querySelector('main h1');
    if (heading) {
      heading.setAttribute('tabindex', '-1');
      heading.focus({ preventScroll: true });
    }
  }

  document.addEventListener('click', (event) => {
    const link = event.target.closest(pageSelector);

    if (!shouldHandle(link, event)) {
      return;
    }

    event.preventDefault();
    loadPage(link.href, true).catch(() => {
      window.location.href = link.href;
    });
  });

  window.addEventListener('popstate', () => {
    loadPage(window.location.href, false).catch(() => {
      window.location.reload();
    });
  });

  // ---------------------------------------------------------------------
  // Init
  // ---------------------------------------------------------------------

  setActiveNav(window.location.href);
  hydrateReleaseData();
})();
