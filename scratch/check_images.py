import zipfile
import xml.etree.ElementTree as ET

with zipfile.ZipFile('отчет фронтенд.docx') as z:
    xml_content = z.read('word/document.xml')
    tree = ET.fromstring(xml_content)
    
    # Let's inspect paragraphs and drawings
    ns = {
        'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
        'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
        'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    }
    
    for i, p in enumerate(tree.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p')):
        texts = [t.text for t in p.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t') if t.text]
        text_str = ''.join(texts)
        drawings = p.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing')
        blips = p.findall('.//{http://schemas.openxmlformats.org/drawingml/2006/main}blip')
        embeds = [b.attrib.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed') for b in blips]
        
        if text_str or embeds:
            print(f'P{i}: "{text_str}" | images: {embeds}')
