import xml.etree.ElementTree as ET

def test_xml():
    tree = ET.parse('/home/ai-server-2/aidt-odoo/custom-addons/aidt_meeting_minutes/views/meeting_recording_views.xml')
    root = tree.getroot()
    form_view = None
    for record in root.findall('record'):
        if record.attrib.get('id') == 'view_meeting_recording_form':
            form_view = record
            break
    
    if form_view is None:
        raise Exception("view_meeting_recording_form not found")
        
    arch_field = form_view.find(".//field[@name='arch']")
    arch_xml = ET.tostring(arch_field, encoding='unicode')
    
    if 'o_dashboard_viewer_container' not in arch_xml:
        print("FAIL: o_dashboard_viewer_container not found in arch")
        exit(1)
        
    if 'o_dashboard_card' not in arch_xml:
        print("FAIL: o_dashboard_card not found in arch")
        exit(1)

    print("PASS: dashboard classes found in view")
    exit(0)

if __name__ == "__main__":
    test_xml()
