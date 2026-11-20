# QNS Web Bridge

Open Quilibrium `.q` websites in Brave using a local bridge and extension.

## Install

On Linux with Python 3, OpenSSL, `certutil`, Brave, and systemd user services:

```sh
git clone https://github.com/0xEnos/qns-web-bridge.git
cd qns-web-bridge
./install.sh
```

Then open `brave://extensions`, enable **Developer mode**, choose **Load unpacked**, and select the repository's `extension/` directory. Open the extension popup and click a site in **Shared .q directory**, or enter a `.q` name.

The installer creates a local CA and bridge for that computer. It does not install the extension automatically. The CA and private key stay under `~/.local/share/qns-bridge/`; never share that directory.

## Shared directory

The extension downloads one public JSON directory from this repository and shows the published sites in its popup. The bridge caches the whole file for up to one hour. It does not ask a per-name resolver when a person visits a listed `.q` site, and this project does not contact `proxima.auction`.

The directory currently contains curated associations maintained in this repository. Everyone can browse those entries without a GitHub account. Saving an association with the extension currently saves it only on that computer; it does not publish it for other users. Do not put QStorage credentials or private keys in the extension. A static public bucket or manifest can distribute a directory, but cannot safely accept anonymous updates by itself.

The registry host can observe when the full directory is downloaded and the downloader's IP address. It does not learn which entry is opened from that download.

## Current shared entry

`obscura.q` points to the public QStorage bucket `0xenos`. Add only names you own or are authorized to publish. Curated entries are statements by the repository maintainer, not cryptographic proof of QNS ownership.

## Files

- `extension/`: Brave extension.
- `local/`: local HTTPS/SOCKS bridge, certificate setup, and systemd user service.
- `registry/`: public shared directory and association publisher page.

The extension is distributed as an unpacked developer extension; it is not published in the Chrome Web Store.

## Limits

- Each user needs the bridge and local `.q` certificate authority on their own computer.
- Associations saved in the popup are local to that installation. The shared directory is read-only for users.
- Browser cookies and storage for `example.q` are separate from those for its destination website.
- The bridge does not currently proxy WebSockets.
