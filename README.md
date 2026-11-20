# QNS Web Bridge

QNS Web Bridge lets Brave open a Quilibrium `.q` name over HTTPS while keeping
that name in the address bar. It consists of a small Brave extension and a
local HTTPS/SOCKS bridge. A signed registry record can associate a name with a
public server IP or a QStorage bucket.

## Install on Linux

Requirements: Python 3, OpenSSL, `certutil` (for example, `libnss3-tools` on
Linux Mint), Brave, and systemd user services.

1. Run `./install.sh`. It creates a Python environment, installs a local CA
   certificate limited to `.q` names in the current user's NSS store, and
   starts the local bridge.
2. In `brave://extensions`, enable Developer mode and choose **Load unpacked**;
   select this repository's `extension/` directory.
3. Enter an owned name such as `example.q` in the extension.

The CA and its private key stay under `~/.local/share/qns-bridge/`. Do not copy
or publish that directory. The bridge listens on loopback only: SOCKS5 port
17777, HTTPS port 17778, and local API port 17779.

## Publish a destination

In the extension, enter the `.q` name and either a public server IP or the
QStorage bucket name. The owner signs a message with the wallet that controls
that QNS name. Signing does not submit a blockchain transaction. The signed
record is shared through the registry so other Web Bridge users can discover
the destination without entering the server address themselves.

The included client currently uses `proxima.auction` for the shared registry
and publication API. To operate a separate registry, update `REGISTRY` and
`PUBLISH_API` in `local/bridge_v2.py`, and configure the matching Caddy route
and publication service for that host.

## Deployment files

- `extension/`: Brave extension and owner-signature page.
- `local/`: local HTTPS/SOCKS bridge, certificate setup, and user service.
- `registry/`: shared publication API and reverse-proxy snippet.

The extension is currently distributed as an unpacked developer extension;
it is not yet published in the Chrome Web Store.

## Limitations

- QNS's **Set Resolved Address** field is for a Quilibrium address, not a web
  URL. Web destinations use the separate owner-signed registry record.
- Each user needs the local bridge and its local `.q` certificate authority;
  the extension alone cannot provide HTTPS for `.q` names.
- The relay does not currently proxy WebSockets, which some web apps require.
- Browser cookies and storage for `example.q` are separate from those for its
  destination website.
