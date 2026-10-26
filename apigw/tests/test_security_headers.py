from fastapi.testclient import TestClient


def test_security_headers_present_on_success_response(client: TestClient):
    response = client.get("/docs")
    assert (
        response.headers.get("Strict-Transport-Security")
        == "max-age=31536000; includeSubDomains"
    )
    assert response.headers.get("Content-Security-Policy").startswith(
        "default-src 'self';"
    )
    assert response.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert (
        response.headers.get("Referrer-Policy")
        == "strict-origin-when-cross-origin"
    )
    assert (
        response.headers.get("Permissions-Policy")
        == "geolocation=(), microphone=(self), camera=()"
    )


def test_security_headers_present_on_api_response(client: TestClient):
    response = client.get("/api/bricks")
    assert (
        response.headers.get("Strict-Transport-Security")
        == "max-age=31536000; includeSubDomains"
    )
    assert response.headers.get("Content-Security-Policy").startswith(
        "default-src 'self';"
    )
    assert response.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert (
        response.headers.get("Referrer-Policy")
        == "strict-origin-when-cross-origin"
    )
    assert (
        response.headers.get("Permissions-Policy")
        == "geolocation=(), microphone=(self), camera=()"
    )


def test_security_headers_present_on_error_response(client: TestClient):
    response = client.get("/api/non-existent-route-xyz")
    assert (
        response.headers.get("Strict-Transport-Security")
        == "max-age=31536000; includeSubDomains"
    )
    assert response.headers.get("Content-Security-Policy").startswith(
        "default-src 'self';"
    )
    assert response.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert (
        response.headers.get("Referrer-Policy")
        == "strict-origin-when-cross-origin"
    )
    assert (
        response.headers.get("Permissions-Policy")
        == "geolocation=(), microphone=(self), camera=()"
    )
