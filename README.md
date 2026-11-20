# QNS Web Sites for Brave

Open the supported Quilibrium `.q` website `obscura.q` in Brave with this
extension. This version uses a small, built-in redirect and needs no Python
bridge, local certificate, local name mapping, Proxima service, or account.

## Install

1. Download the repository ZIP from GitHub and extract it.
2. In Brave, open `brave://extensions` and enable **Developer mode**.
3. Choose **Load unpacked** and select the `extension/` folder.
4. Enter `https://obscura.q` in the address bar, or open the extension popup
   and choose **obscura.q**.

The address bar changes to `https://0xenos.qstorage.quilibrium.com`. The
extension redirects the exact `obscura.q` main-page navigation to that public
QStorage HTTPS origin. Page paths, query strings, and fragments are preserved.
Other browser traffic is not redirected.

## What other people can see

Anyone can view the public Obscura site from their own computer by installing
this extension and opening `obscura.q`. They do not need to be on your device,
use your GitHub account, or run a service on your computer. They can also open
the public QStorage address directly in an ordinary browser.

The extension does **not** publish a visitor's own website, discover all `.q`
names, or automatically add a site just because someone installs or uses it.
For a website to be visible to other people, its files must already be served
from a public web origin. For it to open under a `.q` alias, that alias must
also have a route in a distributed extension build. This build contains only
`obscura.q`; adding another alias requires updating and distributing the
extension. A normal user cannot silently change the routes for everybody.

So: other users can see **your public Obscura site** with this build. You can
see someone else's public site only if it has a public URL and a supported
`.q` route (or they give you the ordinary public URL). Installing the extension
alone does not make either person's private or locally hosted files public.

## Why the URL changes

Brave extensions cannot provide a DNS resolver for the browser or install a
TLS certificate authority. This extension therefore redirects the supported
`.q` name to the site's real HTTPS origin. Keeping `obscura.q` in the address
bar would require browser-level QNS support or a local/network resolver and
HTTPS proxy, which this simplified extension-only build intentionally avoids.

This is a compatibility route to public QStorage content, not universal native
QNS resolution and not an anonymous Quilibrium proxy. It does not claim that
the QNS protocol itself currently resolves every `.q` name to a web origin.

## Tests

Run the route checks with Node.js:

```sh
node tests/test_extension_routes.js
```

The independent Brave smoke test opens the live site using a temporary browser
profile and this extension only. It requires Brave and Python `aiohttp`:

```sh
python3 -m pip install aiohttp
python3 tests/extension_only_acceptance.py
```

The test does not touch the regular Brave profile. The extension has no
QStorage credentials or other administrative secrets.
