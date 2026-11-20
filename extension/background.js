'use strict';

// Only one-label .q names use the local bridge. Every other host is direct.
const PAC = `function FindProxyForURL(url, host) {
  if (/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\\.q$/i.test(host)) {
    return 'SOCKS5 127.0.0.1:17777';
  }
  return 'DIRECT';
}`;

async function installProxy() {
  await chrome.proxy.settings.set({
    value: {mode: 'pac_script', pacScript: {data: PAC}},
    scope: 'regular',
  });
}

chrome.runtime.onInstalled.addListener(() => { installProxy().catch(console.error); });
chrome.runtime.onStartup.addListener(() => { installProxy().catch(console.error); });
installProxy().catch(console.error);

chrome.runtime.onMessage.addListener((message, sender, reply) => {
  if (sender.id !== chrome.runtime.id || !['list', 'save', 'delete', 'directory'].includes(message?.type)) return;
  const name = String(message.name || '');
  if (message.type === 'directory') {
    fetch('http://127.0.0.1:17779/api/directory', {headers: {'X-QNS-Bridge': '1'}})
      .then(async response => {
        const body = await response.text();
        if (!response.ok) throw new Error(body || `HTTP ${response.status}`);
        reply({ok: true, data: JSON.parse(body)});
      }).catch(error => reply({ok: false, error: String(error.message || error)}));
    return true;
  }
  const suffix = message.type === 'delete' ? '/' + encodeURIComponent(name) : '';
  const method = message.type === 'save' ? 'POST' : message.type === 'delete' ? 'DELETE' : 'GET';
  fetch('http://127.0.0.1:17779/api/mappings' + suffix, {
    method,
    headers: {'Content-Type': 'application/json', 'X-QNS-Bridge': '1'},
    body: method === 'POST' ? JSON.stringify({name, destination: message.destination}) : undefined,
  }).then(async response => {
    const body = await response.text();
    if (!response.ok) throw new Error(body || `HTTP ${response.status}`);
    reply({ok: true, data: JSON.parse(body)});
  }).catch(error => reply({ok: false, error: String(error.message || error)}));
  return true;
});
