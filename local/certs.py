"""Issue locally trusted TLS certificates only for one-label .q names."""

import re
import subprocess
from pathlib import Path

DATA_DIR = Path.home() / ".local/share/qns-bridge"
NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.q$")


def run(*args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def create_ca():
    DATA_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    key = DATA_DIR / "ca.key"
    cert = DATA_DIR / "ca.crt"
    if key.exists() and cert.exists():
        return cert
    run(
        "openssl", "req", "-x509", "-newkey", "rsa:3072", "-sha256", "-nodes",
        "-keyout", str(key), "-out", str(cert), "-days", "1825",
        "-subj", "/CN=QNS Web Bridge local CA",
        "-addext", "basicConstraints=critical,CA:TRUE,pathlen:0",
        "-addext", "keyUsage=critical,keyCertSign,cRLSign",
        "-addext", "nameConstraints=critical,permitted;DNS:.q",
    )
    key.chmod(0o600)
    return cert


def create_leaf(name):
    if not NAME_RE.fullmatch(name):
        raise ValueError("Invalid .q name")
    create_ca()
    # Keep the previous 0.2 certificate intact during the upgrade.
    stem = DATA_DIR / (name + ".bridge")
    key = Path(str(stem) + ".key")
    cert = Path(str(stem) + ".crt")
    if key.exists() and cert.exists():
        return cert, key
    request = Path(str(stem) + ".csr")
    extensions = Path(str(stem) + ".ext")
    extensions.write_text(
        "subjectAltName=DNS:" + name + "\n"
        "basicConstraints=critical,CA:FALSE\n"
        "keyUsage=critical,digitalSignature,keyEncipherment\n"
        "extendedKeyUsage=serverAuth\n"
    )
    try:
        run("openssl", "req", "-new", "-newkey", "rsa:2048", "-nodes",
            "-keyout", str(key), "-out", str(request), "-subj", "/CN=" + name)
        key.chmod(0o600)
        run("openssl", "x509", "-req", "-in", str(request),
            "-CA", str(DATA_DIR / "ca.crt"), "-CAkey", str(DATA_DIR / "ca.key"),
            "-CAcreateserial", "-out", str(cert), "-days", "365", "-sha256",
            "-extfile", str(extensions))
    finally:
        request.unlink(missing_ok=True)
        extensions.unlink(missing_ok=True)
    return cert, key


def install_trust():
    cert = create_ca()
    old = Path.home() / ".pki/nssdb"
    current = Path.home() / ".local/share/pki/nssdb"
    # Chromium/Brave versions and distro builds consult different per-user NSS
    # databases. Trust the local CA in both user stores; never touch system-wide
    # trust or another browser profile.
    locations = list(dict.fromkeys([old, current]))
    for location in locations:
        location.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not (location / "cert9.db").exists():
            run("certutil", "-N", "-d", "sql:" + str(location), "--empty-password")
        nickname = "QNS Web Bridge local CA"
        subprocess.run(
            ["certutil", "-D", "-d", "sql:" + str(location), "-n", nickname],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        run("certutil", "-A", "-d", "sql:" + str(location), "-n", nickname,
            "-t", "C,,", "-i", str(cert))


if __name__ == "__main__":
    install_trust()
    create_leaf("stonks.q")
