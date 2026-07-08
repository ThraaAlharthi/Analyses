from compute_stats import compute_stats

# Test 1 — good image returns correct shape
def test_correct_output_shape():
    result = compute_stats("sample.tif", region="test")
    assert "ndvi" in result
    assert "land_cover" in result
    assert "mean" in result["ndvi"]
    assert "vegetation_pct" in result["land_cover"]
    print("✅ Test 1 passed: correct output shape")

# Test 2 — missing file raises error
def test_missing_file():
    try:
        compute_stats("nonexistent.tif")
        print("❌ Test 2 failed: should have raised error")
    except FileNotFoundError:
        print("✅ Test 2 passed: FileNotFoundError raised correctly")

# Test 3 — NDVI values are within valid range
def test_ndvi_range():
    result = compute_stats("sample.tif")
    assert result["ndvi"]["min"] >= -1.0
    assert result["ndvi"]["max"] <= 1.0
    print("✅ Test 3 passed: NDVI values in valid range")

# Run all tests
test_correct_output_shape()
test_missing_file()
test_ndvi_range()
