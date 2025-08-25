"""
Pipeline orchestration for submittal extraction.
Production-ready modular implementation.
"""

import os
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
from .types import Product, ExtractionResult
from .io_adapters import process_with_datalab_cached, extract_text_from_datalab, pdf_to_images_cached
from .stage1 import extract_all_candidates
from .stage2 import judge_visual_selection
from .json_utils import coerce_items_to_products

def full_pipeline(pdf_path: str) -> Dict:
    """Run complete extraction pipeline."""
    pdf_name = Path(pdf_path).name
    print(f"\n{'='*60}")
    print(f"Processing: {pdf_name}")

    try:
        # Step 1: Datalab extraction
        datalab_result = process_with_datalab_cached(pdf_path)

        # Step 2: Extract text
        text = extract_text_from_datalab(datalab_result)
        print(f"Extracted {len(text)} chars of text")

        # Step 3: Convert to images
        images = pdf_to_images_cached(pdf_path)
        print(f"Converted {len(images)} pages to images")

        # Step 4: Extract all candidates
        all_candidates_text, parsed, items = extract_all_candidates(text, pdf_name)
        print(f"Stage 1: Found {len(items)} items")

        # Map ALL items -> Product so downstream is uniform
        products_all = coerce_items_to_products(items, pdf_name=pdf_name)
        print(f"Stage 1: Coerced to {len(products_all)} Product objects")

        # Step 5: Judge with visual context (use RAW text)
        judge = judge_visual_selection(images, all_candidates_text)
        selected_ids = judge.get("selected_ids", []) or []
        print(f"Stage 2: Selected {len(selected_ids)} indices -> {selected_ids}")

        # Step 6: Build selected Product list by index
        products_selected = [products_all[i] for i in selected_ids if 0 <= i < len(products_all)]
        print(f"Stage 2: Selected {len(products_selected)} products")

        print(f"Stage 2: Evidence -> {judge.get('evidence', '')}")
        print("Stage 2: Judge payload ->", judge)

        return {
            "success": True,
            "evidence": judge.get("evidence", ""),
            "products": [p.model_dump() for p in products_selected],
            "candidates": [p.model_dump() for p in products_all],  # Keep for debugging
            "judge_response": {
                "selected_ids": selected_ids,
                "evidence": judge.get("evidence", "")
            }
        }
    except Exception as e:
        print(f"Error: {e}")
        return {"success": False, "error": str(e), "products": []}

class SubmittalExtractor:
    """Main extractor class for easy instantiation and use."""
    
    def __init__(self):
        # Check for required environment variables
        if not os.getenv("ANTHROPIC_API_KEY"):
            print("Warning: ANTHROPIC_API_KEY not set")
        if not os.getenv("DATALAB_API_KEY"):
            print("Warning: DATALAB_API_KEY not set")
    
    def extract_products(self, pdf_path: str) -> List[Product]:
        """Extract products from a PDF file and return list of Product objects."""
        result = full_pipeline(pdf_path)
        if result["success"]:
            return [Product(**p) for p in result["products"]]
        else:
            print(f"Extraction failed: {result.get('error', 'Unknown error')}")
            return []
    
    def extract_with_details(self, pdf_path: str) -> Dict:
        """Extract products with detailed pipeline information."""
        return full_pipeline(pdf_path)

__all__ = ["full_pipeline", "SubmittalExtractor"]