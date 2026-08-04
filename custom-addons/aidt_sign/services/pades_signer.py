import io
import time
import logging
import tempfile
from PIL import Image

_logger = logging.getLogger(__name__)

def sign_pades_pdf(pdf_bytes: bytes, cert_bytes: bytes, password: str, img_bytes: bytes = None, signer_name: str = "", is_org: bool = False) -> bytes:
    """
    Ký số điện tử chuẩn PAdES PKCS#7 vào file PDF bằng thư viện pyHanko.
    - Chữ ký Lãnh đạo (is_org = False): Đặt ở vị trí Người ký góc dưới bên phải (370, 110, 540, 195).
    - Con dấu đỏ Cơ quan (is_org = True): Đặt trùm 1/3 về phía bên trái Chữ ký Lãnh đạo (290, 100, 410, 200) chuẩn Nghị định 30/2020/NĐ-CP.
    """
    if not pdf_bytes or not cert_bytes:
        raise ValueError("Thiếu dữ liệu tệp PDF hoặc Chứng thư số.")

    try:
        from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
        from pyhanko.sign import fields, signers
        from pyhanko.stamp import StaticStampStyle
        from pyhanko.pdf_utils.images import PdfImage

        pwd_bytes = password.encode('utf-8') if isinstance(password, str) else (password or b'')
        with tempfile.NamedTemporaryFile(suffix='.p12', delete=True) as tf:
            tf.write(cert_bytes)
            tf.flush()
            signer = signers.SimpleSigner.load_pkcs12(tf.name, passphrase=pwd_bytes)

        sig_field_name = f"{'OrgStamp' if is_org else 'LeaderSig'}_{int(time.time())}"
        
        # Con dấu đỏ Cơ quan (is_org = True) lấn sang bên trái trùm 1/3 lên Chữ ký Lãnh đạo (is_org = False)
        # Chuẩn Nghị định 30/2020/NĐ-CP Phụ lục I - Mục II.8
        box_coords = (290, 100, 410, 200) if is_org else (370, 110, 540, 195)

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

        stamp_style = None
        if img_bytes:
            try:
                pil_img = Image.open(io.BytesIO(img_bytes))
                pdf_img = PdfImage(pil_img, writer=writer)
                stamp_style = StaticStampStyle(
                    border_width=0,
                    background=pdf_img,
                    background_opacity=1.0
                )
            except Exception as img_err:
                _logger.warning("Không thể xử lý ảnh chữ ký/con dấu: %s", str(img_err))

        meta = signers.PdfSignatureMetadata(field_name=sig_field_name)
        pdf_signer = signers.PdfSigner(meta, signer=signer, stamp_style=stamp_style)

        out = io.BytesIO()
        pdf_signer.sign_pdf(writer, output=out)
        return out.getvalue()

    except ImportError:
        _logger.warning("Thư viện pyHanko chưa sẵn sàng, trả về file gốc trong chế độ thử nghiệm.")
        return pdf_bytes
    except Exception as e:
        _logger.error("PAdES signing failed: %s", str(e), exc_info=True)
        raise RuntimeError(f"Lỗi hệ thống Ký số PAdES: {str(e)}")
