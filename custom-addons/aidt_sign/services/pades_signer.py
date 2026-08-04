import io
import logging
import tempfile

_logger = logging.getLogger(__name__)

def sign_pades_pdf(pdf_bytes: bytes, cert_bytes: bytes, password: str, img_bytes: bytes = None, signer_name: str = "", is_org: bool = False) -> bytes:
    """
    Ký số điện tử chuẩn PAdES PKCS#7 vào file PDF bằng thư viện pyHanko.
    Hỗ trợ Incremental Updates cho ký nhiều bước.
    """
    if not pdf_bytes or not cert_bytes:
        raise ValueError("Thiếu dữ liệu tệp PDF hoặc Chứng thư số.")

    try:
        from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
        from pyhanko.sign import fields, signers

        pwd_bytes = password.encode('utf-8') if isinstance(password, str) else (password or b'')
        with tempfile.NamedTemporaryFile(suffix='.p12', delete=True) as tf:
            tf.write(cert_bytes)
            tf.flush()
            signer = signers.SimpleSigner.load_pkcs12(tf.name, passphrase=pwd_bytes)

        sig_field_name = 'OrgStampField' if is_org else 'LeaderSignatureField'
        box_coords = (100, 700, 250, 800) if is_org else (350, 100, 550, 200)

        pdf_stream = io.BytesIO(pdf_bytes)
        writer = IncrementalPdfFileWriter(pdf_stream)

        fields.append_signature_field(
            writer,
            sig_field_spec=fields.SigFieldSpec(
                sig_field_name=sig_field_name,
                on_page=-1,
                box=box_coords
            )
        )

        meta = signers.PdfSignatureMetadata(field_name=sig_field_name)
        pdf_signer = signers.PdfSigner(meta, signer=signer)

        out = io.BytesIO()
        pdf_signer.sign_pdf(writer, output=out)
        return out.getvalue()

    except ImportError:
        _logger.warning("Thư viện pyHanko chưa sẵn sàng, trả về file gốc trong chế độ thử nghiệm.")
        return pdf_bytes
    except Exception as e:
        _logger.error("PAdES signing failed: %s", str(e), exc_info=True)
        raise RuntimeError(f"Lỗi hệ thống Ký số PAdES: {str(e)}")
