import base64
import logging

_logger = logging.getLogger(__name__)

# xmlid (in aidt_org_demo) -> sample text content, spread across secrecy levels
# so the file-inheritance / N-04 demo shows every tier:
#   doc_tu_01    -> thuong
#   doc_btc_01   -> mat
#   doc_tccb_01  -> toi_mat
#   doc_ubkt_01  -> toi_mat
#   doc_nv1_01   -> tuyet_mat
SAMPLE_DOC_XMLIDS = [
    'aidt_org_demo.doc_tu_01',
    'aidt_org_demo.doc_btc_01',
    'aidt_org_demo.doc_tccb_01',
    'aidt_org_demo.doc_ubkt_01',
    'aidt_org_demo.doc_nv1_01',
]


def _sanitize_file_name(base):
    """Mirror aidt_document._dir_name(): strip characters the DMS file-name
    check rejects ('/' and NUL)."""
    base = (base or 'tep-mau').replace('/', '-').replace('\x00', '').strip()
    return base or 'tep-mau'


def post_init_hook(env):
    """Attach one sample .txt dms.file to the directory of a handful of demo
    documents, spread across secrecy levels, so the document<->DMS bridge and
    the N-04 secrecy inheritance are demoable out of the box.

    Idempotent: skips a document if a file with the computed name already
    exists in its directory (safe to re-run on module upgrade/reinstall).
    """
    DmsFile = env['dms.file'].sudo()
    content = base64.b64encode(
        'Noi dung tep mau phuc vu demo N-04 do mat / bridge van ban - DMS.'.encode('utf-8')
    )

    for xmlid in SAMPLE_DOC_XMLIDS:
        doc = env.ref(xmlid, raise_if_not_found=False)
        if not doc:
            _logger.warning(
                "aidt_dms_demo: khong tim thay van ban demo '%s', bo qua.", xmlid
            )
            continue
        if not doc.directory_id:
            _logger.warning(
                "aidt_dms_demo: van ban '%s' chua co thu muc DMS (directory_id "
                "rong), bo qua.", doc.display_name
            )
            continue

        file_name = _sanitize_file_name(f"{doc.reference or doc.name}.txt")

        existing = DmsFile.search([
            ('directory_id', '=', doc.directory_id.id),
            ('name', '=', file_name),
        ], limit=1)
        if existing:
            continue

        DmsFile.create({
            'name': file_name,
            'directory_id': doc.directory_id.id,
            'content': content,
        })
