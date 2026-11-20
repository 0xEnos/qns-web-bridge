# QNS Web Bridge

QNS Web Bridge opens the bundled `obscura.q` site in a separate Brave profile. It provides local SOCKS5 routing and HTTPS termination for `.q` names whose associations are included in the bundled manifest. It is not a universal QNS resolver or an anonymous Quilibrium proxy.

## Linux install

Install Brave first if it is not already installed. Then download and extract the Linux package, or clone the repository, and run:

```sh
./install.sh
```

The installer checks for Python 3.10+, OpenSSL, NSS `certutil`, systemd user services, and Brave. It creates a private Python virtual environment using the exact package versions in `requirements-linux.lock`, issues and trusts the local `.q` certificate authority, enables the per-user bridge service, and opens `https://obscura.q/` in the dedicated `QNS Web Bridge` profile. It does not change system-wide certificate trust, another browser's data, or Brave's ordinary profile. If system packages are missing, rerun with `./install.sh --install-deps`; the installer displays the package list and requires confirmation before using apt, dnf, or pacman.

Use `./qns-web-bridge.sh` to start the bridge if needed and open the dedicated Brave profile later. To open another bundled `.q` name, pass it as an argument, such as `./qns-web-bridge.sh https://obscura.q/`.

## Certificate scope and data

The bridge creates its own CA and per-name leaf certificates under `~/.local/share/qns-bridge/`. The directory is mode `0700`, private keys are mode `0600`, and the CA has a critical `DNS:.q` name constraint. The trust entry is added only to `~/.pki/nssdb`. Chromium/Brave uses a shared NSS database on Linux; current versions default to `~/.local/share/pki/nssdb` but use `~/.pki/nssdb` when it exists. Creating the compatibility database lets old and current Brave builds use the same trust entry. No system trust store or second NSS database is changed. [Chromium's Linux certificate documentation](https://chromium.googlesource.com/chromium/src/+/main/docs/linux/cert_management.md) describes this lookup behavior.

**Brave on Linux does not use a per-profile NSS database for trusted roots.** The dedicated browser profile keeps cookies, extensions, and browsing data separate, but the `.q`-constrained CA trust is shared by Brave profiles under this operating-system account. Other applications that explicitly use this NSS database may also see the CA, still limited by the `.q` name constraint. This is the remaining limitation of local HTTPS for `.q` in Brave; the installer avoids broad system trust.

The CA private key is local and must not be shared. The bridge only routes one-label `.q` names through its local SOCKS5 listener; other sites remain direct. Browser cookies and storage remain per `.q` origin.

## Association fallback

`obscura.q → QStorage bucket 0xenos` is bundled in `registry/manifest.json`. The bridge tries the configured QStorage manifest first, then this bundled manifest, then the public GitHub fallback. If QStorage is temporarily unavailable, the bundled association still resolves. There is no per-visit name lookup. Users do not need GitHub or QStorage credentials. The manifest host can see its own download traffic and client IP addresses.

## Uninstall

Run:

```sh
./uninstall.sh
```

This stops and disables the per-user bridge service, removes its service file, and removes the bridge CA trust entry from the user NSS database. It keeps the CA key, certificates, local mappings, and dedicated Brave profile unless explicitly requested. To permanently delete local CA and mapping data, use `./uninstall.sh --purge-data` and confirm the prompt. To also delete the dedicated Brave profile and its cookies/browser data, add `--purge-profile` and confirm its separate prompt.

After uninstalling, the downloaded or cloned application directory can be deleted.

## Verification

Build a deterministic Linux source bundle with:

```sh
scripts/package-linux.sh
```

This creates `dist/qns-web-bridge-linux-0.6.3.tar.gz`; it does not publish a release.

Run the automated tests with the install's virtual environment or any environment containing the requirements:

```sh
./.venv/bin/python -m unittest discover -s tests -v
tests/install_smoke.sh
./.venv/bin/python tests/acceptance.py
```

`install_smoke.sh` uses a temporary HOME and fake systemd/Brave commands. It never modifies the machine's active service or browser. `acceptance.py` creates a fresh install, simulates a QStorage manifest HTTP 503, restarts an isolated bridge process, verifies the bundled fallback and TLS certificate, and opens the site in a real headless Brave process with the unpacked extension loaded. It uses a temporary HOME, browser profile, and alternate test ports so it cannot collide with the user's regular Brave or existing bridge. The current Obscura page has inline CSS/JavaScript and no same-origin links; the acceptance test checks those actual page features and same-origin fragment navigation.

## Current limitations

- Only bundled associations are available. Arbitrary `.q` name resolution and ownership verification are not implemented.
- The bridge currently does not proxy WebSockets.
- The publisher UI is not required to open the bundled site and does not publish globally shared associations.
