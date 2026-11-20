import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("openssl") and shutil.which("certutil"),
                     "OpenSSL and NSS certutil are required")
class CertificateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="qns-certs-test-")
        self.home = Path(self.temp.name)
        self.env = os.environ.copy()
        self.env["HOME"] = str(self.home)
        self.env["PYTHONPATH"] = str(ROOT / "local")
        subprocess.run([sys.executable, str(ROOT / "local/certs.py")],
                       env=self.env, check=True, capture_output=True)
        subprocess.run([sys.executable, "-c",
                        "from certs import create_leaf; create_leaf('obscura.q')"],
                       env=self.env, check=True, capture_output=True)
        self.data = self.home / ".local/share/qns-bridge"

    def tearDown(self):
        self.temp.cleanup()

    def test_private_key_permissions_and_single_user_nss_store(self):
        self.assertEqual(self.data.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.data / "ca.key").stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.data / "obscura.q.bridge.key").stat().st_mode & 0o777, 0o600)
        self.assertTrue((self.home / ".pki/nssdb/cert9.db").is_file())
        self.assertFalse((self.home / ".local/share/pki/nssdb/cert9.db").exists())
        trust = subprocess.run(
            ["certutil", "-L", "-d", "sql:" + str(self.home / ".pki/nssdb")],
            check=True, capture_output=True, text=True,
        ).stdout
        self.assertIn("QNS Web Bridge local CA", trust)

    def test_ca_is_constrained_and_obscura_leaf_verifies(self):
        verify = subprocess.run(
            ["openssl", "verify", "-CAfile", str(self.data / "ca.crt"),
             "-verify_hostname", "obscura.q", str(self.data / "obscura.q.bridge.crt")],
            capture_output=True, text=True,
        )
        self.assertEqual(verify.returncode, 0, verify.stderr)
        constraints = subprocess.run(
            ["openssl", "x509", "-in", str(self.data / "ca.crt"), "-noout", "-text"],
            check=True, capture_output=True, text=True,
        ).stdout
        self.assertIn("X509v3 Name Constraints: critical", constraints)
        self.assertIn("DNS:.q", constraints)

    def test_ca_rejects_a_non_q_certificate(self):
        csr = self.data / "outside.csr"
        key = self.data / "outside.key"
        cert = self.data / "outside.crt"
        ext = self.data / "outside.ext"
        ext.write_text("subjectAltName=DNS:outside.example\nextendedKeyUsage=serverAuth\n")
        subprocess.run(["openssl", "req", "-new", "-newkey", "rsa:2048", "-nodes",
                        "-keyout", str(key), "-out", str(csr), "-subj", "/CN=outside.example"],
                       check=True, capture_output=True)
        key.chmod(0o600)
        subprocess.run(["openssl", "x509", "-req", "-in", str(csr), "-CA", str(self.data / "ca.crt"),
                        "-CAkey", str(self.data / "ca.key"), "-CAcreateserial", "-out", str(cert),
                        "-days", "1", "-extfile", str(ext)], check=True, capture_output=True)
        verify = subprocess.run(
            ["openssl", "verify", "-CAfile", str(self.data / "ca.crt"),
             "-verify_hostname", "outside.example", str(cert)],
            capture_output=True, text=True,
        )
        self.assertNotEqual(verify.returncode, 0)
        self.assertIn("permitted subtree violation", (verify.stdout + verify.stderr).lower())


if __name__ == "__main__":
    unittest.main()
