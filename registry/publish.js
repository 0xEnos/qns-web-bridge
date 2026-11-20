'use strict';

const form = document.getElementById('publish');
const status = document.getElementById('status');
const namePattern = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.q$/;

// Values entered in the extension are carried here, so the owner signs one
// shared publication instead of creating an app-local mapping first.
const params = new URLSearchParams(location.search);
if (params.has('name')) document.getElementById('name').value = params.get('name');
if (params.get('kind') === 'ip' && params.has('ip')) {
  document.getElementById('destination').value = params.get('ip');
  if (params.has('host') && params.get('host')) {
    document.getElementById('host-details').hidden = false;
    document.getElementById('server-host').value = params.get('host');
  }
} else if (params.get('kind') === 'qstorage' && params.has('bucket')) {
  document.getElementById('destination').value = params.get('bucket');
}

function destinationFromFields() {
  const value = document.getElementById('destination').value.trim();
  const isIp = value.includes(':') || /^\d{1,3}(?:\.\d{1,3}){3}$/.test(value);
  return isIp
    ? {kind: 'ip', ip: value, host: document.getElementById('server-host').value.trim()}
    : {kind: 'qstorage', bucket: value};
}
document.getElementById('destination').addEventListener('input', () => {
  const value = document.getElementById('destination').value.trim();
  document.getElementById('host-details').hidden = !(value.includes(':') || /^\d{1,3}(?:\.\d{1,3}){3}$/.test(value));
});

form.addEventListener('submit', async event => {
  event.preventDefault();
  status.textContent = 'Vérification de votre nom QNS…';
  try {
    const name = document.getElementById('name').value.trim().toLowerCase();
    if (!namePattern.test(name)) throw new Error('Indiquez un nom comme monsite.q.');
    const destination = destinationFromFields();
    if (!window.ethereum) throw new Error('Ouvrez cette page dans Brave avec votre portefeuille QNS.');
    const response = await fetch('https://names.quilibrium.com/resolve/' + name.slice(0, -2));
    if (!response.ok) throw new Error('Ce nom QNS est introuvable.');
    const qns = await response.json();
    const owner = qns.header?.authorityKey;
    const [account] = await window.ethereum.request({method: 'eth_requestAccounts'});
    if (account?.toLowerCase() !== owner?.toLowerCase()) {
      throw new Error('Connectez le portefeuille qui détient ce nom sur QNS.');
    }
    const timestamp = Math.floor(Date.now() / 1000);
    const nonce = Array.from(crypto.getRandomValues(new Uint8Array(16)), x => x.toString(16).padStart(2, '0')).join('');
    const encoded = JSON.stringify(Object.fromEntries(Object.entries(destination).sort(([a], [b]) => a.localeCompare(b))));
    const message = `QNS Web Bridge v3\nName: ${name}\nDestination: ${encoded}\nTimestamp: ${timestamp}\nNonce: ${nonce}`;
    status.textContent = 'Confirmez la signature dans votre portefeuille…';
    const signature = await window.ethereum.request({method: 'personal_sign', params: [message, account]});
    const endpoint = location.hostname.endsWith('.q')
      ? '/.qns-web-bridge/api/publish' : '/api/qns-bridge/publish';
    const result = await fetch(endpoint, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({name, destination, timestamp, nonce, signature}),
    });
    if (!result.ok) throw new Error(await result.text());
    const label = destination.kind === 'ip' ? destination.ip + (destination.host ? ' · ' + destination.host : '') : destination.bucket + '.qstorage.quilibrium.com';
    status.textContent = `${name} est publié vers ${label}. Vous pouvez partager https://${name}/`;
    if (location.hostname === name) {
      setTimeout(() => location.replace('https://' + name + '/'), 900);
    }
  } catch (error) {
    status.textContent = error.message || String(error);
  }
});
