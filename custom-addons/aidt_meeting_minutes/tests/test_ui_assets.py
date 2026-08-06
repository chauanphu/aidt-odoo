try:
    from odoo.tests.common import TransactionCase
except ImportError:
    TransactionCase = object
import ast

class TestUIAssets(TransactionCase):
    def test_manifest_assets(self):
        """Ensure the new SCSS file is listed in the manifest"""
        with open('custom-addons/aidt_meeting_minutes/__manifest__.py', 'r') as f:
            manifest = ast.literal_eval(f.read())
        assets = manifest.get('assets', {}).get('web.assets_backend', [])
        self.assertIn('aidt_meeting_minutes/static/src/scss/meeting_dashboard.scss', assets)

import os

def test_scss_contains_premium_tokens():
    scss_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'src', 'scss', 'meeting_dashboard.scss')
    with open(scss_path, 'r') as f:
        content = f.read()
    
    assert '.premium-dashboard-container' in content, "Missing .premium-dashboard-container class"
    assert '.premium-card' in content, "Missing .premium-card class"
    assert 'backdrop-filter: blur' in content, "Missing glassmorphism blur"
    assert 'box-shadow' in content, "Missing soft shadow"

if __name__ == '__main__':
    test_scss_contains_premium_tokens()
    print("SCSS premium tokens test passed!")
