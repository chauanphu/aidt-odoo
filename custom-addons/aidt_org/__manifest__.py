{
    'name': 'AIDT Tổ chức & Văn bản',
    'version': '1.0',
    'category': 'Human Resources',
    'summary': 'Cây tổ chức, RBAC vai trò, phân quyền phạm vi văn bản (N-02/N-03/N-05)',
    'depends': ['hr', 'mail'],
    'data': [
        'security/aidt_org_groups.xml',
        'security/ir.model.access.csv',
        'security/aidt_org_rules.xml',
        'data/aidt_clearance.xml',
        'views/aidt_document_views.xml',
        'views/hr_department_views.xml',
        'views/res_users_views.xml',
    ],
    'license': 'LGPL-3',
}
