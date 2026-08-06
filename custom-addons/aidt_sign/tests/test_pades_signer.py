import pathlib
import unittest

from pyhanko.sign import signers

from odoo.addons.aidt_sign.services.pades_signer import sign_pades_pdf


CERT_DIR = pathlib.Path(__file__).parents[1] / "data" / "certs"


class TestPadesSigner(unittest.TestCase):
    def test_demo_personal_certificate_matches_configured_password(self):
        signer = signers.SimpleSigner.load_pkcs12(
            CERT_DIR / "sample_cert_van_an.p12", passphrase=b"123456"
        )
        self.assertIsNotNone(signer)

    def test_demo_organisation_certificate_matches_configured_password(self):
        signer = signers.SimpleSigner.load_pkcs12(
            CERT_DIR / "sample_cert_co_quan.p12", passphrase=b"123456"
        )
        self.assertIsNotNone(signer)

    def test_invalid_certificate_reports_actionable_error(self):
        with self.assertRaisesRegex(
            RuntimeError,
            "Không thể mở chứng thư số.*mật khẩu",
        ):
            sign_pades_pdf(b"%PDF-1.4\n", b"not a pkcs12 file", "wrong")

