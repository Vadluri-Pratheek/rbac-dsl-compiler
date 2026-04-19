import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app


def test_index_page_renders():
    client = app.test_client()
    response = client.get("/")

    assert response.status_code == 200
    assert b"RBAC DSL Policy Compiler" in response.data
    assert b"Analyze Policy" in response.data


def test_analyze_endpoint_filters_invalid_graph_edges_and_colors_nodes():
    client = app.test_client()
    response = client.post(
        "/analyze",
        json={
            "code": """
role Admin inherits Ghost {
    permissions: root
}
conflict Admin, Shadow
assign Admin to Alice
"""
        },
    )

    assert response.status_code == 200

    data = response.get_json()
    assert data["success"] is True
    assert data["graph"]["nodes"] == [{"id": "Admin", "color": "high_priv"}]
    assert data["graph"]["edges"] == []
    assert any("undefined" in entry["message"].lower() for entry in data["errors"])


def test_analyze_endpoint_returns_empty_graph_for_syntax_errors():
    client = app.test_client()
    response = client.post(
        "/analyze",
        json={"code": "role Admin { permissions: read"},
    )

    assert response.status_code == 200

    data = response.get_json()
    assert data["success"] is False
    assert data["graph"] == {"nodes": [], "edges": []}
    assert data["summary"]["verdict"] == "UNSAFE"
    assert data["errors"]


def test_analyze_endpoint_surfaces_security_warnings_and_risks():
    client = app.test_client()
    response = client.post(
        "/analyze",
        json={
            "code": """
role Viewer {
    permissions: read, read
}
role User {
    permissions: browse
}
role Admin {
    permissions: root
}
role Intern inherits Admin {
    permissions: browse
}
"""
        },
    )

    assert response.status_code == 200

    data = response.get_json()
    assert data["success"] is True
    assert len(data["warnings"]) == 1
    assert len(data["risks"]) == 1
    assert "Redundant permission" in data["warnings"][0]["message"]
    assert "Privilege Escalation" in data["risks"][0]["message"]


def test_fix_endpoint_returns_ascii_safe_preview():
    client = app.test_client()
    response = client.post(
        "/fix",
        json={
            "code": """
role Viewer {
    permissions: read
}
role Admin {
    permissions: root
}
conflict Viewer, Admin
assign Viewer to Alice
assign Admin to Alice
"""
        },
    )

    assert response.status_code == 200

    data = response.get_json()
    assert data["success"] is True
    assert "# [HEURISTIC-REVIEW]" in data["fixed_code"]
    assert "Manual review required -" in data["fixed_code"]
    assert all(ord(ch) < 128 for ch in data["fixed_code"])
    assert all(all(ord(ch) < 128 for ch in entry["description"]) for entry in data["changelog"])
