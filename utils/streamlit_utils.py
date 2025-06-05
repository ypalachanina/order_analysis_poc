import requests
import base64
from io import BytesIO
from PIL import Image
import os
from pathlib import Path


def load_image_from_web(url):
    response = requests.get(url)
    img = Image.open(BytesIO(response.content))

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    base64_img = base64.b64encode(buffer.getvalue()).decode()

    data_uri = f"data:image/png;base64,{base64_img}"
    return data_uri


def load_local_image(image_path):
    if os.path.exists(image_path):
        with open(image_path, "rb") as img_file:
            img_data = img_file.read()
            img_b64 = base64.b64encode(img_data).decode()

            file_ext = Path(image_path).suffix.lower()
            if file_ext in ['.jpg', '.jpeg']:
                mime_type = 'image/jpeg'
            elif file_ext == '.png':
                mime_type = 'image/png'
            else:
                mime_type = 'image/png'  # default to png
            return f"data:{mime_type};base64,{img_b64}"
    return None
