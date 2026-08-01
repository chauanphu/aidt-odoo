"""Cầu import tới aidt_format_engine.

Cùng một thư viện có hai đường import tuỳ môi trường: lúc Odoo chạy thì nó
nằm dưới namespace `odoo.addons`; lúc chạy pytest thì `custom-addons` nằm
trên sys.path nên import thẳng. Đây là module DUY NHẤT trong
aidt_search_engine được phép nhắc tới `odoo`.
"""

try:                                        # trong Odoo
    from odoo.addons.aidt_format_engine import parser as fe_parser
    from odoo.addons.aidt_format_engine import types as fe_types
    from odoo.addons.aidt_format_engine import zones as fe_zones
except ImportError:                         # pytest ngoài Odoo
    from aidt_format_engine import parser as fe_parser
    from aidt_format_engine import types as fe_types
    from aidt_format_engine import zones as fe_zones

__all__ = ["fe_parser", "fe_types", "fe_zones"]
