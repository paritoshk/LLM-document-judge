#!/usr/bin/env python3
"""
Simple CLI for the submittal extractor
"""

import sys
import json
from pathlib import Path

# Add src to path  
sys.path.insert(0, str(Path(__file__).parent))

from src.pipeline import full_pipeline


def main():
    if len(sys.argv) != 2:
        print("Usage: python cli.py <pdf_path>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    if not Path(pdf_path).exists():
        print(f"Error: File {pdf_path} not found")
        sys.exit(1)
    
    print(f"Processing: {pdf_path}")
    result = full_pipeline(pdf_path)
    
    if result["success"]:
        products = result["products"]
        print(json.dumps(products, indent=2))
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()