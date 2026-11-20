# QNS Web Bridge

QNS Web Bridge lets Brave open a Quilibrium `.q` name over HTTPS while keeping
that name in the address bar. It consists of a small Brave extension and a
local HTTPS/SOCKS bridge. A signed record can associate a name with a public
server IP or a QStorage bucket.

## Privacy model

- A personal mapping saved in the extension is resolved locally and takes
  precedence over the shared directory.
- Shared associations come from one public JSON manifest. The default is the
  public GitHub raw file in this repository; a user can point
  `QNS_BRIDGE_REGISTRY_URL` to a copy in their own QStorage bucket.
- The bridge downloads the same whole manifest on the first shared lookup and
  refreshes it at most once per hour. It does not request a name-specific
  record, and normal `.q` visits do not call a QNS resolver. The host can see
  the manifest download time and client IP, but not which entry the user opens.
- Local mappings take precedence and make no directory request. Manifest
  entries marked `curated` are trusted as statements by this repository's
  maintainer; wallet-signed entries are also supported and verified. A wallet
  signature proves who signed, not that the wallet owns the QNS name.

The official QNS SDK currently uses an HTTP resolver endpoint rather than
exposing a direct protocol-proof resolver to this bridge. This project therefore
does not claim that its manifest is a direct Q protocol lookup; it shares a
curated directory without per-visit name queries.

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

## Share a site with all extension users

The repository's public `registry/manifest.json` is the shared directory. Add
an entry for a site you own or are authorized to publish, then commit and push
the change. Every bridge downloads the same complete file; lookups are local.
For example:

```json
{
  "name": "example.q",
  "curated": true,
  "destination": {"kind": "qstorage", "bucket": "mybucket"}
}
```

The manifest is publicly readable. To use a copy in your own QStorage bucket,
set `QNS_BRIDGE_REGISTRY_URL` to its public object URL. The repository also
supports signed records, but their signatures identify the signer rather than
prove QNS ownership.


## Deployment files

- `extension/`: Brave extension.
- `local/`: local HTTPS/SOCKS bridge, certificate setup, and user service.
- `registry/`: signed-entry publisher page, manifest builder, and empty
  manifest template.

The extension is distributed as an unpacked developer extension; it is not yet
published in the Chrome Web Store.

## Limitations

- Curated manifest entries rely on users trusting the repository maintainer.
  Only add names you own or have permission to publish.
- QNS's **Set Resolved Address** field is for a Quilibrium address, not a web
  URL. Web destinations use the signed Web Bridge association.
- Each user needs the local bridge and its local `.q` certificate authority;
  the extension alone cannot provide HTTPS for `.q` names.
- The relay does not currently proxy WebSockets, which some web apps require.
- Browser cookies and storage for `example.q` are separate from those for its
  destination website.
