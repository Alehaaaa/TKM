# TheKeyMachine Website

Static website branch for TheKeyMachine.

Live site: https://alehaaaa.github.io/TKM/

This branch is independent from the application source branches and contains only the files needed for GitHub Pages.

Canonical pages:

- `index.html`
- `changelog/index.html`
- `about/index.html`
- `help/index.html`

The root `changelog.html`, `about.html`, and `help.html` files only preserve old
links by redirecting them to the clean directory routes.

Shared runtime data and presentation:

- `site.js`
- `styles.css`
- `releases.json`

Assets:

- `images/web_logo_230.png`
- `images/favicon.png`
- `images/github.svg`
- `images/youtube.svg`
- `images/instagram.svg`
- `images/discord.svg`

The release workflow on `main` generates the homepage release panel, the full
static changelog, and `releases.json` from the same records. The JSON powers
search and client-side enhancement, while the generated HTML keeps downloads,
release notes, navigation, Help, and About usable when JavaScript is disabled.
