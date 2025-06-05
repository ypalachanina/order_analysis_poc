import xml.etree.ElementTree as ET


def read_xml_file(xml_path: str) -> str:
    encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252']
    for encoding in encodings:
        try:
            with open(xml_path, 'r', encoding=encoding) as file:
                return file.read()
        except UnicodeDecodeError:
            continue

    with open(xml_path, 'rb') as file:
        content = file.read()
        return content.decode('utf-8', errors='ignore')


def validate_xml(xml_string: str) -> bool:
    try:
        ET.fromstring(xml_string)
        return True
    except ET.ParseError as e:
        print(f"XML validation error: {e}")
        return False


def save_xml(xml_string: str, output_path: str) -> None:
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(xml_string)
    print(f"XML saved to: {output_path}")
