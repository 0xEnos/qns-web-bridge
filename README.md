# QNS Web Bridge

QNS Web Bridge lets Brave open a Quilibrium `.q` name over HTTPS while keeping
that name in the address bar. It consists of a small Brave extension and a
local HTTPS/SOCKS bridge. A signed record can associate a name with a public
server IP or a QStorage bucket.

## Privacy model

- A personal mapping saved in the extension is resolved locally and takes
  precedence over the shared directory.
- Shared associations come from one static JSON manifest in the QStorage
  bucket configured by `QNS_BRIDGE_REGISTRY_URL` (default:
  `https://0xenos1.qstorage.quilibrium.com/qns-web-bridge/registry.json`).
- The bridge downloads the same whole manifest on the first shared lookup and
  refreshes it at most once per hour. It does not request a name-specific
  record, and normal `.q` visits do not call `names.quilibrium.com` or another
  QNS resolver.
- The manifest and each entry are public. The bucket can observe requests for
  the manifest, but not which entry a user opens. Users who need to avoid even
  that bucket request can use personal local mappings only.
- A wallet signature proves which wallet signed an association. It does not,
  by itself, prove that the wallet currently owns the QNS name. The maintainer
  of a shared manifest must verify the QNS owner before accepting an entry.

The official QNS SDK currently uses an HTTP resolver endpoint rather than
exposing a direct protocol-proof resolver to this bridge. This project therefore
does not claim that its manifest is a direct Q protocol lookup; it removes
per-visit name queries and the third-party per-name registry.

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

## Publish an association

1. In the extension, enter the `.q` name and either a public server IP or a
   QStorage bucket name.
2. Sign the proposed association in the wallet. This is a local message
   signature; it does not submit a transaction or contact a registry.
3. The bridge stores the signed entry locally and downloads a JSON file.
   Resolve the ownership question before sharing it: confirm that the signing
   wallet is the current QNS owner.
4. Collect verified entry files and build a manifest:

   ```sh
   python3 registry/build_manifest.py registry/entries
   ```

   The command verifies every signature and writes `registry/manifest.json`.
   Upload that file to the public QStorage bucket as
   `qns-web-bridge/registry.json`.

The extension does not contain QStorage write credentials. Uploading the
manifest is a deliberate bucket-owner action. To use another bucket, set
`QNS_BRIDGE_REGISTRY_URL` in the bridge service environment to that bucket's
public manifest URL and restart the local service.

## Deployment files

- `extension/`: Brave extension.
- `local/`: local HTTPS/SOCKS bridge, certificate setup, and user service.
- `registry/`: signed-entry publisher page, manifest builder, and empty
  manifest template.

The extension is distributed as an unpacked developer extension; it is not yet
published in the Chrome Web Store.

## Limitations

- The shared manifest is curated. A valid wallet signature alone is not proof
  that the signer owns the corresponding QNS name.
- QNS's **Set Resolved Address** field is for a Quilibrium address, not a web
  URL. Web destinations use the signed Web Bridge association.
- Each user needs the local bridge and its local `.q` certificate authority;
  the extension alone cannot provide HTTPS for `.q` names.
- The relay does not currently proxy WebSockets, which some web apps require.
- Browser cookies and storage for `example.q` are separate from those for its
  destination website.
