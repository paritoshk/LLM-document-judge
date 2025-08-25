"""JSON parsing utilities for LLM outputs"""

import re
import json
from typing import List, Dict
from .types import Product

def _first_top_level_json_block(text: str) -> str:
    """
    Forcefully extract the first JSON object/array.
    - Strips code fences/wrappers.
    - Finds the first '{' or '['.
    - Scans to the end, auto-closing any unbalanced braces/brackets and an
      unterminated string if needed.
    - Returns the candidate JSON *string*. Never raises; if nothing found,
      returns the original text trimmed (caller can decide what to do).
    """
    s = text.lstrip("\ufeff").strip()

    # Remove ```json fences if present
    if s.startswith("```"):
        s = re.sub(r"^```(?:json|JSON)?\s*\n?", "", s, flags=re.M)
        s = re.sub(r"\n?```$", "", s)

    # Strip very simple XML/HTML wrappers if any
    s = re.sub(r"^\s*<[^>]+>\s*", "", s)
    s = re.sub(r"\s*</[^>]+>\s*$", "", s)

    # Locate first JSON opener
    i1, i2 = s.find("{"), s.find("[")
    starts = [i for i in (i1, i2) if i != -1]
    if not starts:
        return s  # no opener; return as-is (handled later)

    i = min(starts)

    # Scan and auto-balance
    stack = []
    in_str = False
    esc = False
    j = i
    n = len(s)
    while j < n:
        c = s[j]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c in "{[":
                stack.append(c)
            elif c in "}]":
                if stack:
                    top = stack[-1]
                    if (top == "{" and c == "}") or (top == "[" and c == "]"):
                        stack.pop()
        j += 1

    block = s[i:j]
    # Close unterminated string
    if in_str:
        block += '"'
    # Close any remaining open containers
    while stack:
        top = stack.pop()
        block += "}" if top == "{" else "]"

    return block


def _clean_json_minor_issues(s: str) -> str:
    """
    Clean common JSON issues WITHOUT raising:
    - Remove JS-style comments
    - Remove trailing commas before '}' or ']'
    - Normalize NBSP and smart quotes
    - Strip BOM and control chars
    Returns cleaned string.
    """
    if not s:
        return s

    # Strip BOM
    s = s.lstrip("\ufeff")

    # Remove //... and /* ... */ comments
    s = re.sub(r"(?m)//.*?$", "", s)
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)

    # Remove trailing commas before } or ]
    s = re.sub(r",(\s*[}\]])", r"\1", s)

    # Normalize spaces/quotes
    s = s.replace("\u00A0", " ")
    s = s.replace(""", '"').replace(""", '"').replace("'", "'")

    # Drop unprintable control chars (except tab/newline/carriage return)
    s = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", s)

    return s

def coerce_items_to_products(items: List[dict], pdf_name: str) -> List[Product]:
    """Convert list of dict items to Product objects with fallbacks."""
    out: List[Product] = []
    for i, r in enumerate(items):
        if not isinstance(r, dict):
            r = {}

        # Try to derive product_name
        product_name = (
            r.get("product_name") or r.get("name") or r.get("title") or
            r.get("product") or "Unknown Product"
        )

        # Try to derive variant_identifier
        variant_identifier = (
            r.get("variant_identifier") or r.get("series") or r.get("series_type") or
            r.get("type") or r.get("model") or str(i)
        )

        # Try to derive product_family and manufacturer; fallbacks are conservative
        product_family = r.get("product_family") or r.get("family") or "Unknown Family"
        manufacturer = r.get("manufacturer") or r.get("brand") or "Unknown Manufacturer"

        out.append(Product(
            product_name=str(product_name),
            variant_identifier=str(variant_identifier),
            product_family=str(product_family),
            manufacturer=str(manufacturer),
        ))
    return out

def _product_schema_block() -> str:
    """JSON schema for Claude."""
    schema = {
        "type": "object",
        "properties": {
            "products": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "product_name": {"type": "string"},
                        "variant_identifier": {"type": "string"},
                        "product_family": {"type": "string"},
                        "manufacturer": {"type": "string"},
                    },
                    "required": ["product_name", "variant_identifier", "product_family", "manufacturer"],
                },
            },
            "confidence_score": {"type": "number", "minimum": 0, "maximum": 1},
            "annotation_type": {"type": "string", "enum": ["highlight", "box", "circle", "none", "unknown"]},
            "page_numbers": {"type": "array", "items": {"type": "integer"}},
        },
        "required": ["products"],
    }
    return json.dumps(schema, ensure_ascii=False)

__all__ = ["_first_top_level_json_block", "_clean_json_minor_issues", "coerce_items_to_products", "_product_schema_block"]