"""Data types and models for submittal extraction"""

import json
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator


class Product(BaseModel):
    product_name: str = Field(description="Human-readable product name")
    variant_identifier: str = Field(description="Key distinguishing feature")
    product_family: str = Field(description="Product family name")
    manufacturer: str = Field(description="Manufacturer name")


class AnnotationType(str, Enum):
    HIGHLIGHT = "highlight"
    BOX = "box"
    CIRCLE = "circle"
    NONE = "none"
    UNKNOWN = "unknown"


class ExtractionResult(BaseModel):
    products: List[Product] = Field(default_factory=list)
    confidence_score: Optional[float] = None
    annotation_type: AnnotationType = AnnotationType.UNKNOWN
    page_numbers: List[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def _compute_defaults(cls, values):
        conf = values.confidence_score or (0.7 if values.products else 0.0)
        values.confidence_score = min(1.0, max(0.0, conf))
        try:
            values.page_numbers = sorted({int(p) for p in values.page_numbers})
        except:
            values.page_numbers = []
        return values


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