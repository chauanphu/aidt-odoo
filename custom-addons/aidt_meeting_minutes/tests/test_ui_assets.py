from odoo.tests.common import TransactionCase
import ast

class TestUIAssets(TransactionCase):
    def test_manifest_assets(self):
        """Ensure the new SCSS file is listed in the manifest"""
        with open('custom-addons/aidt_meeting_minutes/__manifest__.py', 'r') as f:
            manifest = ast.literal_eval(f.read())
        assets = manifest.get('assets', {}).get('web.assets_backend', [])
        self.assertIn('aidt_meeting_minutes/static/src/scss/meeting_dashboard.scss', assets)
