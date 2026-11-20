'use strict';

const $ = id => document.getElementById(id);
const NAME = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.q$/;

function normalizeName(value) {
  const name = value.trim().toLowerCase().replace(/^https?:\/\//, '').replace(/\/$/, '');
  if (!NAME.test(name)) throw new Error('Saisissez un nom comme monsite.q');
  return name;
}

function setStatus(message) { $('status').textContent = message; }

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
