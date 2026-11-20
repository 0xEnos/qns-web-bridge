# QNS Web Sites (extension-only prototype)

This branch tests the simplest Brave-only path for the public `obscura.q` site.
Install the unpacked `extension/` directory, then open `https://obscura.q` or
choose it from the extension popup. The extension redirects that navigation to
the site's public QStorage HTTPS origin, `https://0xenos.qstorage.quilibrium.com`.
The same route is packaged with the extension, so every installation of this
version gets the same result without local setup, a certificate, a Python
bridge, a personal mapping, or a GitHub account.

## Install for a local test

1. Open `brave://extensions`.
2. Enable **Developer mode** and click **Load unpacked**.
3. Select this repository's `extension/` directory.
4. Open `https://obscura.q`.

The first navigation changes the address bar to the public QStorage URL. This
is required by the extension-only design: Brave extensions cannot add a `.q`
DNS resolver or install a TLS authority, so they cannot keep `.q` as the final
HTTPS origin without a local/network proxy or browser support for QNS.

## Current scope and limits

- `obscura.q` is the only packaged route. Other `.q` names are not assumed to
  host websites and are left untouched.
- This is shared through distribution of the extension version, not through a
  live directory. Adding a route requires a new extension build/update.
- QNS currently resolves names to QNS records, but the public SDK/API does not
  document a website-destination field that this extension can consume. The
  packaged route is therefore a compatibility mapping, not proof that
  `obscura.q` currently has an on-network QNS website record.
- Public site content is still served by QStorage Proxy. This extension does
  not make traffic anonymous or provide universal native QNS resolution.

## Verify this branch

```sh
node tests/test_extension_routes.js
python3 tests/extension_only_acceptance.py
```

The acceptance test needs Brave and Python `aiohttp`. It launches a separate,
temporary Brave profile and opens the live QStorage site; it does not touch the
normal Brave profile. The legacy bridge tests can also be run with
`python3 -m unittest tests.test_bridge tests.test_certs` in an environment with
the dependencies from `requirements.txt`.

## Legacy bridge files

`local/`, `install.sh`, and the older registry publisher are retained for
reference and compatibility while this prototype is evaluated. The extension
in this branch no longer configures the local proxy or calls those files.
