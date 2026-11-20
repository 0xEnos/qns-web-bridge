# QNS Web Bridge

Open Quilibrium `.q` websites in Brave through a local HTTPS/SOCKS bridge.

## Install on Linux

With Python 3, OpenSSL, `certutil`, Brave and systemd user services:

```sh
git clone https://github.com/0xEnos/qns-web-bridge.git
cd qns-web-bridge
./install.sh
```

The installer creates a local certificate authority, installs and starts the bridge, then opens a dedicated Brave profile with the extension loaded and `obscura.q` opened. No mapping or extension setup is required. Continue using that QNS Web Bridge profile for `.q` sites; it is separate from your regular Brave profile and does not share its extensions or cookies.

The CA and private key remain under `~/.local/share/qns-bridge/`; never share that folder.

## Bundled shared association

The extension reads QStorage `0xenos1` first and falls back to the repository's public manifest. The current minimal entry is `obscura.q → 0xenos`. It is loaded automatically by the bridge and used in autocomplete; the name can also be typed directly. The reader never needs QStorage credentials, wallet access, or a GitHub account. No service contacts `proxima.auction`.

At times the QStorage manifest may be unavailable. The bundled GitHub fallback keeps `obscura.q` accessible. The host serving the manifest can see downloads and client IPs, but the bridge does not make a per-visit name lookup.

## Limits

- Installing/running the local bridge and loading the extension are automated by `install.sh` and `launch-brave.sh`. The dedicated profile is used because browser policy does not permit silently installing an unpacked extension into an existing regular profile.
- Only names with a bundled association can be opened this way today. Decentralized QNS resolution for arbitrary `.q` names is not implemented yet.
- Browser cookies and storage for `example.q` are separate from those for its destination website.
- The bridge does not currently proxy WebSockets.
