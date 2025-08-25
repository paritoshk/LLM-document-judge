"""I/O adapters for PDF processing and image conversion"""

import os
import time
import pickle
import requests
import re
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
from typing import List, Dict, Tuple
from io import BytesIO
import base64
import logfire

# Configure logfire
LOGFIRE_TOKEN = os.getenv("LOGFIRE_TOKEN")
if LOGFIRE_TOKEN:
    logfire.configure(token=LOGFIRE_TOKEN)
else:
    logfire.configure()

# Configuration
USE_CACHE = True
CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)

@logfire.instrument("datalab.process")
def process_with_datalab_cached(file_path: str) -> Dict:
    """Process PDF with Datalab, saving polling URL for resumption."""
    DATALAB_API_KEY = os.getenv("DATALAB_API_KEY")
    if not DATALAB_API_KEY:
        raise ValueError("DATALAB_API_KEY environment variable not set")
    
    cache_key = f"datalab_{Path(file_path).stem}"
    cache_file = CACHE_DIR / f"{cache_key}.pkl"
    url_file = CACHE_DIR / f"{cache_key}_url.txt"

    # Check if we have a complete result
    if USE_CACHE and cache_file.exists():
        with open(cache_file, 'rb') as f:
            data = pickle.load(f)
            if data.get("status") == "complete":
                print(f"Loaded complete result from cache: {cache_key}")
                return data

    # Check if we have a polling URL to resume
    if USE_CACHE and url_file.exists():
        check_url = url_file.read_text().strip()
        print(f"Resuming polling from saved URL: {check_url}")
        headers = {"X-API-Key": DATALAB_API_KEY}
        for _ in range(300):
            r = requests.get(check_url, headers=headers)
            data = r.json()
            if data.get("status") == "complete":
                with open(cache_file, 'wb') as f:
                    pickle.dump(data, f)
                url_file.unlink()  # Remove URL file after completion
                print(f"Completed and cached: {cache_key}")
                return data
            if data.get("status") == "error":
                raise Exception(f"Datalab failed: {data.get('error')}")
            time.sleep(2)

    # Fresh submission
    print(f"Submitting to Datalab: {Path(file_path).name}")

    MARKER_CONFIG = {
        "use_llm": True,
        "force_ocr": True,
        "output_format": "json",
        "paginate": True,
        "strip_existing_ocr": False,
        "disable_image_extraction": False,
        "debug": True,
    }

    url = "https://www.datalab.to/api/v1/marker"
    headers = {"X-API-Key": DATALAB_API_KEY}

    with open(file_path, "rb") as file:
        files = {"file": (os.path.basename(file_path), file, "application/pdf")}
        response = requests.post(url, files=files, data=MARKER_CONFIG, headers=headers)

    if response.status_code != 200:
        raise Exception(f"Datalab error: {response.text}")

    result = response.json()
    check_url = result.get("request_check_url")

    # Save polling URL
    if check_url:
        url_file.write_text(check_url)
        print(f"Saved polling URL: {url_file.name}")

    # Poll for completion
    for _ in range(300):
        r = requests.get(check_url, headers=headers)
        data = r.json()
        if data.get("status") == "complete":
            with open(cache_file, 'wb') as f:
                pickle.dump(data, f)
            if url_file.exists():
                url_file.unlink()
            print(f"Saved to cache: {cache_key}")
            return data
        if data.get("status") == "error":
            raise Exception(f"Datalab failed: {data.get('error')}")
        time.sleep(2)

    raise TimeoutError("Datalab polling timeout")

@logfire.instrument("text.extract")
def extract_text_from_datalab(datalab_result: Dict) -> str:
    """Extract text from Datalab JSON."""
    full_text = ""
    try:
        for page in datalab_result.get("json", {}).get("children", []):
            for block in page.get("children", []):
                if "html" in block:
                    text = re.sub("<[^<]+?>", "", block["html"])
                    if text.strip():
                        full_text += text + "\n"
    except Exception as e:
        print(f"Text extraction error: {e}")
    return full_text

@logfire.instrument("images.render")
def pdf_to_images_cached(pdf_path: str, max_pages: int = 10) -> List[Tuple]:
    """Convert PDF to images using pdf2image."""
    cache_key = f"images_{Path(pdf_path).stem}.pkl"
    cache_file = CACHE_DIR / cache_key

    # Try cache first
    if USE_CACHE and cache_file.exists():
        print(f"Loading images from cache: {cache_key}")
        with open(cache_file, 'rb') as f:
            return pickle.load(f)

    print(f"Converting PDF to images: {Path(pdf_path).name}")

    # Using pdf2image
    try:
        from pdf2image import convert_from_path

        # Convert PDF to PIL images
        pil_images = convert_from_path(
            pdf_path,
            dpi=200,  # Good quality
            first_page=1,
            last_page=min(max_pages, 100)
        )

        images = []
        for page_num, pil_img in enumerate(pil_images):
            # Convert PIL to base64
            buffer = BytesIO()
            pil_img.save(buffer, format='PNG')
            img_base64 = base64.b64encode(buffer.getvalue()).decode()
            images.append((page_num, "image/png", img_base64))
            print(f"  Page {page_num}: {len(img_base64)} bytes (base64)")

    except ImportError:
        print("pdf2image not available")
        images = []

    # Save to cache
    if USE_CACHE and images:
        with open(cache_file, 'wb') as f:
            pickle.dump(images, f)
        print(f"Saved {len(images)} images to cache: {cache_key}")

    return images

__all__ = ["process_with_datalab_cached", "extract_text_from_datalab", "pdf_to_images_cached"]