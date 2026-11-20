'use strict';

// Packaged routes work offline and identically on every installation of this
// extension version. A QNS name only maps to a public website when its owner
// has a route here; native QNS records currently do not expose a documented
// web-destination field.
const ROUTES = Object.freeze({
  'obscura.q': 'https://0xenos.qstorage.quilibrium.com',
});

function resolveRoute(input) {
  const source = new URL(input);
  const host = source.hostname.toLowerCase().replace(/\.$/, '');
  if (!/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.q$/.test(host)) return null;
  const origin = ROUTES[host];
  if (!origin) return null;
  const target = new URL(origin);
  target.pathname = source.pathname;
  target.search = source.search;
  target.hash = source.hash;
  return target.href;
}

// Brave/Chromium extensions cannot install a resolver or TLS authority. The
// packaged declarativeNetRequest rule redirects this exact host before DNS;
// the content is opened from its real public HTTPS origin, so the address bar
// changes to the QStorage URL. It never intercepts non-.q sites.
if (typeof chrome !== 'undefined') {
  chrome.runtime.onMessage.addListener((message, sender, reply) => {
    if (sender.id !== chrome.runtime.id || message?.type !== 'sites') return;
    reply({sites: Object.keys(ROUTES).sort()});
  });
}

// Export only for the lightweight Node tests; Chromium ignores this branch.
if (typeof module !== 'undefined') module.exports = {resolveRoute};
