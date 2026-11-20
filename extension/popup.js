'use strict';

const $ = id => document.getElementById(id);
const NAME = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.q$/;

function normalizeName(value) {
  const name = value.trim().toLowerCase().replace(/^https?:\/\//, '').replace(/\/$/, '');
  if (!NAME.test(name)) throw new Error('Enter a name like mysite.q');
  return name;
}

function setStatus(message) { $('status').textContent = message; }

chrome.runtime.sendMessage({type: 'directory'}, response => {
  if (chrome.runtime.lastError || !response?.ok) return;
  const options = (response.data?.sites || [])
    .filter(site => NAME.test(String(site.name || '').toLowerCase()))
    .map(site => String(site.name).toLowerCase());
  $('shared-sites').replaceChildren(...[...new Set(options)].sort().map(name => {
    const option = document.createElement('option');
    option.value = name;
    return option;
  }));
});

$('open-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const name = normalizeName($('open-name').value);
    await chrome.tabs.create({url: 'https://' + name + '/'});
    window.close();
  } catch (error) { setStatus(error.message); }
});

function destinationFromFields() {
  const value = $('destination').value.trim();
  const isIp = value.includes(':') || /^\d{1,3}(?:\.\d{1,3}){3}$/.test(value);
  return isIp
    ? {kind: 'ip', ip: value, host: $('server-host').value.trim()}
    : {kind: 'qstorage', bucket: value};
}

$('destination').addEventListener('input', () => {
  const value = $('destination').value.trim();
  $('host-details').hidden = !(value.includes(':') || /^\d{1,3}(?:\.\d{1,3}){3}$/.test(value));
});

$('publish-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const name = normalizeName($('name').value);
    const destination = destinationFromFields();
    const params = new URLSearchParams({name, ...destination});
    const url = 'https://' + name + '/.qns-web-bridge/publish?' + params.toString();
    await chrome.tabs.create({url});
    window.close();
  } catch (error) { setStatus(error.message); }
});
