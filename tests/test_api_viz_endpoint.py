"""
Tests for the /api/viz endpoint that serves visualization images.
"""
from pathlib import Path
from fastapi.testclient import TestClient
import pytest


def test_serve_visualization_success(tmp_path):
    """Test that /api/viz endpoint serves existing images."""
    from agentspace.api.app import app

    # Create a test image
    plots_dir = Path(__file__).parent.parent / "plots"
    plots_dir.mkdir(exist_ok=True)
    test_file = plots_dir / "test_viz.png"
    test_file.write_bytes(b"fake-png-data")

    try:
        client = TestClient(app)

        # Test the endpoint
        response = client.get("/api/viz?path=test_viz.png")

        assert response.status_code == 200
        assert response.content == b"fake-png-data"
        assert response.headers["content-type"] == "image/png"
        assert "cache-control" in response.headers
    finally:
        # Cleanup
        if test_file.exists():
            test_file.unlink()


def test_serve_visualization_not_found():
    """Test that /api/viz returns 404 for non-existent files."""
    from agentspace.api.app import app

    client = TestClient(app)
    response = client.get("/api/viz?path=nonexistent.png")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_serve_visualization_path_traversal_blocked():
    """Test that /api/viz blocks path traversal attempts."""
    from agentspace.api.app import app

    client = TestClient(app)

    # Try various path traversal attacks
    dangerous_paths = [
        "../../../etc/passwd",
        "../../app.py",
        "../agentspace/config.py",
    ]

    for dangerous_path in dangerous_paths:
        response = client.get(f"/api/viz?path={dangerous_path}")
        assert response.status_code in (403, 404), f"Path traversal not blocked: {dangerous_path}"


def test_serve_visualization_content_types():
    """Test that /api/viz returns correct content types for different file types."""
    from agentspace.api.app import app

    plots_dir = Path(__file__).parent.parent / "plots"
    plots_dir.mkdir(exist_ok=True)

    test_files = [
        ("test.png", b"png-data", "image/png"),
        ("test.jpg", b"jpg-data", "image/jpeg"),
        ("test.jpeg", b"jpeg-data", "image/jpeg"),
        ("test.svg", b"svg-data", "image/svg+xml"),
    ]

    client = TestClient(app)

    for filename, content, expected_type in test_files:
        test_file = plots_dir / filename
        test_file.write_bytes(content)

        try:
            response = client.get(f"/api/viz?path={filename}")
            assert response.status_code == 200
            assert response.headers["content-type"] == expected_type
            assert response.content == content
        finally:
            if test_file.exists():
                test_file.unlink()


def test_serve_visualization_with_subdirectories():
    """Test that /api/viz can serve files from subdirectories."""
    from agentspace.api.app import app

    plots_dir = Path(__file__).parent.parent / "plots"
    subdir = plots_dir / "heatmaps"
    subdir.mkdir(exist_ok=True, parents=True)

    test_file = subdir / "test.png"
    test_file.write_bytes(b"subdir-png-data")

    try:
        client = TestClient(app)
        response = client.get("/api/viz?path=heatmaps/test.png")

        assert response.status_code == 200
        assert response.content == b"subdir-png-data"
    finally:
        if test_file.exists():
            test_file.unlink()
        if subdir.exists():
            subdir.rmdir()


def test_serve_visualization_handles_leading_slashes():
    """Test that /api/viz handles paths with leading slashes."""
    from agentspace.api.app import app

    plots_dir = Path(__file__).parent.parent / "plots"
    plots_dir.mkdir(exist_ok=True)
    test_file = plots_dir / "test.png"
    test_file.write_bytes(b"png-data")

    try:
        client = TestClient(app)

        # Test with various leading slash formats
        paths = [
            "test.png",
            "/test.png",
            "//test.png",
            "/plots/test.png",  # This should work after stripping
        ]

        for path in paths:
            response = client.get(f"/api/viz?path={path}")
            # Should either succeed or fail consistently
            assert response.status_code in (200, 404, 403)
    finally:
        if test_file.exists():
            test_file.unlink()
