import base64
from PyPDF2 import PdfReader, PdfWriter
from pdf2image import convert_from_bytes
from io import BytesIO


def process_page(pdf_reader, page_num):
    page = pdf_reader.pages[page_num]
    output = BytesIO()
    writer = PdfWriter()
    writer.add_page(page)
    writer.write(output)
    page_bytes = output.getvalue()

    images = convert_from_bytes(page_bytes, dpi=200, first_page=1, last_page=1)

    img_buffer = BytesIO()
    images[0].save(img_buffer, format='PNG')
    encoded_content = base64.b64encode(img_buffer.getvalue()).decode("utf-8")

    output.close()
    img_buffer.close()

    return encoded_content


def pdf_to_images(pdf_path):
    encoded_images = []

    with open(pdf_path, 'rb') as file:
        pdf_reader = PdfReader(file)
        for page_num in range(len(pdf_reader.pages)):
            page_encoded = process_page(pdf_reader, page_num)
            encoded_images.append(page_encoded)

    return encoded_images


def pdf_to_text(pdf_path):
    text_content = []

    with open(pdf_path, 'rb') as file:
        pdf_reader = PdfReader(file)
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            page_text = page.extract_text()
            if page_text:
                text_content.append(f"=== Page {page_num + 1} ===\n{page_text}")

    return "\n\n".join(text_content)


def pdf_to_images_and_text(pdf_path):
    encoded_images = pdf_to_images(pdf_path)
    text_content = pdf_to_text(pdf_path)
    return encoded_images, text_content


def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')
