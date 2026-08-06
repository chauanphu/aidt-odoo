{
    "name": "AIDT Base",
    "summary": "Nền chung cho các module tuỳ chỉnh của dự án AIDT",
    "version": "19.0.1.0.0",
    "category": "Technical",
    "license": "LGPL-3",
    "author": "AIDT",
    "depends": ["base", "project", "website", "project_todo"],
    "data": [
        "views/aidt_menu_cleanup.xml",
        "views/aidt_login_templates.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "aidt_base/static/src/css/modal_fix.css",
        ],
    },
    "installable": True,
    "application": False,
}
