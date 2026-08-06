import os
import xml.etree.ElementTree as ET

def test_xml_premium_layout():
    xml_path = os.path.join(os.path.dirname(__file__), '..', 'views', 'meeting_recording_views.xml')
    tree = ET.parse(xml_path)
    root = tree.getroot()
    
    # Check for the premium container
    container = root.find(".//div[@class='premium-dashboard-container']")
    assert container is not None, "Missing <div class='premium-dashboard-container'>"
    
    # Check for the 50/50 layout (at least two col-md-6)
    col_6_elements = root.findall(".//div[@class='col-md-6']")
    assert len(col_6_elements) >= 2, "Main layout must use col-md-6 for a 50/50 split"

if __name__ == '__main__':
    test_xml_premium_layout()
    print("XML premium layout test passed!")
