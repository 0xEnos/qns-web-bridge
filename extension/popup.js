'use strict';

const $ = id => document.getElementById(id);
const NAME = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.q$/;

function normalizeName(value) {
  const name = value.trim().toLowerCase().replace(/^https?:\/\//, '').replace(/\/$/, '');
  if (!NAME.test(name)) throw new Error('Enter a name like mysite.q');
  return name;
}

function setStatus(message) { $('status').textContent = message; }

chrome.runtime.sendMessage({type: 'sites'}, response => {
  if (chrome.runtime.lastError || !response?.sites) return;
  const options = response.sites
    .filter(site => NAME.test(String(site || '').toLowerCase()))
    .map(site => String(site).toLowerCase());
  $('supported-sites').replaceChildren(...[...new Set(options)].sort().map(name => {
    const option = document.createElement('option');
    option.value = name;
    return option;
  }));
});

$('open-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const name = normalizeName($('open-name').value);
    const sites = await new Promise(resolve => {
      chrome.runtime.sendMessage({type: 'sites'}, response => resolve(response?.sites || []));
    });
    if (!sites.includes(name)) throw new Error('This site is not included in this extension version yet.');
    await chrome.tabs.create({url: 'https://' + name + '/'});
    window.close();
  } catch (error) { setStatus(error.message); }
});
