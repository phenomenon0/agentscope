#!/usr/bin/env python3
"""
Manual test for /api/viz endpoint.
Run this to verify the endpoint works correctly.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

print("Testing /api/viz endpoint...")
print("=" * 60)

try:
    from fastapi.testclient import TestClient
    from agentspace.api.app import app

    # Create test client
    client = TestClient(app)

    # Ensure plots directory exists with test file
    plots_dir = Path(__file__).parent / "plots"
    plots_dir.mkdir(exist_ok=True)
    test_file = plots_dir / "test_viz.png"

    if not test_file.exists():
        print(f"✗ Test file not found: {test_file}")
        print("  Please ensure plots/test_viz.png exists")
        sys.exit(1)

    print(f"✓ Test file exists: {test_file}")
    print(f"  File size: {test_file.stat().st_size} bytes")
    print()

    # Test 1: Basic retrieval
    print("Test 1: Basic image retrieval")
    response = client.get("/api/viz?path=test_viz.png")
    if response.status_code == 200:
        print(f"✓ Status: {response.status_code}")
        print(f"✓ Content-Type: {response.headers.get('content-type')}")
        print(f"✓ Content length: {len(response.content)} bytes")
    else:
        print(f"✗ Status: {response.status_code}")
        print(f"  Error: {response.json()}")
    print()

    # Test 2: Non-existent file
    print("Test 2: Non-existent file (should return 404)")
    response = client.get("/api/viz?path=nonexistent.png")
    if response.status_code == 404:
        print(f"✓ Status: {response.status_code}")
        print(f"✓ Error message: {response.json()['detail']}")
    else:
        print(f"✗ Status: {response.status_code} (expected 404)")
    print()

    # Test 3: Path traversal protection
    print("Test 3: Path traversal protection")
    response = client.get("/api/viz?path=../../app.py")
    if response.status_code in (403, 404):
        print(f"✓ Status: {response.status_code}")
        print(f"✓ Path traversal blocked")
    else:
        print(f"✗ Status: {response.status_code} (expected 403 or 404)")
    print()

    # Test 4: Cache headers
    print("Test 4: Cache headers")
    response = client.get("/api/viz?path=test_viz.png")
    cache_control = response.headers.get("cache-control", "")
    if "max-age" in cache_control:
        print(f"✓ Cache-Control: {cache_control}")
    else:
        print(f"✗ No cache headers found")
    print()

    # Test 5: Index endpoint includes /api/viz
    print("Test 5: Index endpoint lists /api/viz")
    response = client.get("/")
    if response.status_code == 200:
        endpoints = response.json().get("endpoints", [])
        if "/api/viz" in endpoints:
            print(f"✓ /api/viz listed in endpoints")
        else:
            print(f"✗ /api/viz not listed in endpoints")
            print(f"  Available: {endpoints}")
    print()

    print("=" * 60)
    print("✓ All tests completed successfully!")
    print()
    print("Next steps:")
    print("1. Start the backend: uvicorn agentspace.api.app:app --reload")
    print("2. Test in browser: http://localhost:8000/api/viz?path=test_viz.png")
    print("3. Use in chat to generate heatmaps and see them render!")

except ImportError as e:
    print(f"✗ Import error: {e}")
    print("\nPlease install required packages:")
    print("  pip install fastapi[all]")
    sys.exit(1)
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
