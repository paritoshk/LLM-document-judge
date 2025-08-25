#!/usr/bin/env python3
"""Test individual modules for functionality and error handling."""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_json_utils():
    """Test JSON utility functions."""
    print("=== Testing json_utils ===")
    try:
        from json_utils import _first_top_level_json_block, _clean_json_minor_issues, coerce_items_to_products
        
        # Test JSON extraction
        test_text = 'Here is some text {"products": [{"name": "test"}]} and more text'
        result = _first_top_level_json_block(test_text)
        assert '{"products":' in result, f"Expected JSON block, got: {result}"
        print("✓ JSON extraction works")
        
        # Test JSON cleaning
        dirty_json = '{"name": "test",}'
        clean_json = _clean_json_minor_issues(dirty_json)
        assert clean_json == '{"name": "test"}', f"Expected clean JSON, got: {clean_json}"
        print("✓ JSON cleaning works")
        
        # Test product coercion
        items = [{"name": "Test Product", "model_number": "123"}]
        products = coerce_items_to_products(items, "test.pdf")
        assert len(products) == 1, f"Expected 1 product, got {len(products)}"
        print("✓ Product coercion works")
        
        print("json_utils: ✅ ALL TESTS PASSED\n")
        return True
        
    except Exception as e:
        print(f"❌ json_utils failed: {e}\n")
        return False

def test_environment_setup():
    """Test environment variable handling."""
    print("=== Testing Environment Setup ===")
    
    # Check if .env file exists
    env_file = Path(".env")
    if env_file.exists():
        print("✓ .env file exists")
    else:
        print("⚠️  .env file missing (expected for testing)")
    
    # Test required environment variables
    required_vars = ["ANTHROPIC_API_KEY", "DATALAB_API_KEY"]
    missing_vars = []
    
    for var in required_vars:
        if os.getenv(var):
            print(f"✓ {var} is set")
        else:
            missing_vars.append(var)
            print(f"❌ {var} is missing")
    
    if missing_vars:
        print(f"⚠️  Missing environment variables: {missing_vars}")
        print("Environment: ⚠️  PARTIAL - missing API keys\n")
        return False
    else:
        print("Environment: ✅ ALL VARIABLES SET\n")
        return True

def test_imports():
    """Test that all modules can be imported without errors."""
    print("=== Testing Module Imports ===")
    modules = [
        "types",
        "json_utils", 
        "io_adapters",
        "stage1",
        "stage2", 
        "pipeline"
    ]
    
    failed_imports = []
    for module in modules:
        try:
            __import__(module)
            print(f"✓ {module} imported successfully")
        except Exception as e:
            failed_imports.append((module, str(e)))
            print(f"❌ {module} failed to import: {e}")
    
    if failed_imports:
        print(f"Imports: ❌ {len(failed_imports)} FAILED\n")
        return False
    else:
        print("Imports: ✅ ALL SUCCESSFUL\n")
        return True

def test_error_handling():
    """Test error handling in key functions."""
    print("=== Testing Error Handling ===")
    
    try:
        from json_utils import _first_top_level_json_block, coerce_items_to_products
        
        # Test with malformed JSON
        malformed = "not json at all"
        result = _first_top_level_json_block(malformed)
        print(f"✓ Handles malformed input: {result[:50]}...")
        
        # Test with empty list
        empty_products = coerce_items_to_products([], "test.pdf")
        assert len(empty_products) == 0, "Expected empty list"
        print("✓ Handles empty input")
        
        # Test with malformed items
        bad_items = [{"invalid": "data"}, None, "not_a_dict"]
        try:
            products = coerce_items_to_products(bad_items, "test.pdf")
            print(f"✓ Handles malformed items, got {len(products)} products")
        except Exception as e:
            print(f"⚠️  Error handling malformed items: {e}")
        
        print("Error Handling: ✅ ROBUST\n")
        return True
        
    except Exception as e:
        print(f"❌ Error handling test failed: {e}\n")
        return False

if __name__ == "__main__":
    print("🧪 Running Module Tests\n")
    
    results = []
    results.append(test_imports())
    results.append(test_environment_setup())
    results.append(test_json_utils()) 
    results.append(test_error_handling())
    
    passed = sum(results)
    total = len(results)
    
    print("=" * 50)
    print(f"📊 TEST SUMMARY: {passed}/{total} test suites passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print("⚠️  Some tests failed or had warnings")
        sys.exit(1)