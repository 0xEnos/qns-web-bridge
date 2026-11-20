# QNS Web Bridge

Open Quilibrium `.q` websites in Brave using a local bridge and extension.

## Install

On Linux with Python 3, OpenSSL, `certutil`, Brave, and systemd user services:

```sh
git clone https://github.com/0xEnos/qns-web-bridge.git
cd qns-web-bridge
./install.sh
```

Then open `brave://extensions`, enable **Developer mode**, choose **Load unpacked**, and select the repository's `extension/` directory. In the popup, type the first letters of a shared `.q` name in the existing **QNS name** field and choose its suggestion, or enter a name directly.

The installer creates a local CA and bridge for that computer. It does not install the extension automatically. The CA and private key stay under `~/.local/share/qns-bridge/`; never share that directory.

## Shared directory

The extension downloads the shared directory from the public QStorage bucket `0xenos1` first, then falls back to this repository's manifest. It uses those names as autocomplete suggestions in the existing QNS field and caches the complete directory for up to one hour. It does not ask a per-name resolver when a person visits a listed `.q` site, and this project does not contact `proxima.auction`.

At the time of this release, `0xenos1` serves the static test page but does not yet contain `registry/manifest.json`, so the extension continues to use the GitHub fallback. The shared manifest contains curated associations maintained in this repository. Everyone can browse them without a GitHub account. Saving an association with the extension still saves it only on that computer; it does not publish it for other users. Do not put QStorage credentials or private keys in the extension. A public QStorage object can distribute the directory, but its write access must be configured safely before automatic public submissions can be enabled.

The registry host can observe when the full directory is downloaded and the downloader's IP address. It does not learn which entry is opened from that download.

## Current shared entry

`obscura.q` points to the public QStorage bucket `0xenos`. Add only names you own or are authorized to publish. Curated entries are statements by the repository maintainer, not cryptographic proof of QNS ownership.

## Files

- `extension/`: Brave extension.
- `local/`: local HTTPS/SOCKS bridge, certificate setup, and systemd user service.
- `registry/`: shared directory source and association-signing page.

The extension is distributed as an unpacked developer extension; it is not published in the Chrome Web Store.

## Limits

- Each user needs the bridge and local `.q` certificate authority on their own computer.
- Associations saved in the popup are local to that installation. Public automatic submissions are not enabled yet.
- Browser cookies and storage for `example.q` are separate from those for its destination website.
- The bridge does not currently proxy WebSockets.
