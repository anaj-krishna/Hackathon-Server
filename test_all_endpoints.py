import httpx
import json
import os
import uuid
import sys

BASE_URL = "http://127.0.0.1:8000"

def generate_minimal_pdf(filename):
    # Standard minimal 1-page PDF
    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj\n"
        b"<<\n"
        b"  /Type /Catalog\n"
        b"  /Pages 2 0 R\n"
        b">>\n"
        b"endobj\n"
        b"2 0 obj\n"
        b"<<\n"
        b"  /Type /Pages\n"
        b"  /Kids [3 0 R]\n"
        b"  /Count 1\n"
        b">>\n"
        b"endobj\n"
        b"3 0 obj\n"
        b"<<\n"
        b"  /Type /Page\n"
        b"  /Parent 2 0 R\n"
        b"  /Resources <<\n"
        b"    /Font <<\n"
        b"      /F1 4 0 R\n"
        b"    >>\n"
        b"  >>\n"
        b"  /MediaBox [0 0 595.275 841.889]\n"
        b"  /Contents 5 0 R\n"
        b">>\n"
        b"endobj\n"
        b"4 0 obj\n"
        b"<<\n"
        b"  /Type /Font\n"
        b"  /Subtype /Type1\n"
        b"  /BaseFont /Helvetica\n"
        b">>\n"
        b"endobj\n"
        b"5 0 obj\n"
        b"<< /Length 44 >>\n"
        b"stream\n"
        b"BT\n"
        b"/F1 12 Tf\n"
        b"72 712 Td\n"
        b"(Requirement: Secure Stripe Payment Integration) Tj\n"
        b"ET\n"
        b"endstream\n"
        b"endobj\n"
        b"xref\n"
        b"0 6\n"
        b"0000000000 65535 f\n"
        b"0000000009 00000 n\n"
        b"0000000058 00000 n\n"
        b"0000000115 00000 n\n"
        b"0000000244 00000 n\n"
        b"0000000311 00000 n\n"
        b"trailer\n"
        b"<<\n"
        b"  /Size 6\n"
        b"  /Root 1 0 R\n"
        b">>\n"
        b"startxref\n"
        b"406\n"
        b"%%EOF\n"
    )
    with open(filename, "wb") as f:
        f.write(pdf_content)

def run_tests():
    # Generate unique credentials
    test_id = str(uuid.uuid4())[:8]
    email = f"test_{test_id}@example.com"
    password = "testpassword123"
    
    print(f"=== Testing with credentials: {email} / {password} ===")

    # 1. GET /health
    print("\n--- [GET] /health ---")
    try:
        resp = httpx.get(f"{BASE_URL}/health")
        print(f"Status: {resp.status_code}")
        print(f"Body: {resp.text}")
    except Exception as e:
        print(f"Request failed: {e}")

    # 2. POST /auth/register
    print("\n--- [POST] /auth/register ---")
    try:
        resp = httpx.post(f"{BASE_URL}/auth/register?email={email}&password={password}")
        print(f"Status: {resp.status_code}")
        print(f"Body: {resp.text}")
    except Exception as e:
        print(f"Request failed: {e}")

    # 3. POST /auth/login
    print("\n--- [POST] /auth/login ---")
    token = None
    try:
        resp = httpx.post(
            f"{BASE_URL}/auth/login",
            data={"username": email, "password": password}
        )
        print(f"Status: {resp.status_code}")
        print(f"Body: {resp.text}")
        if resp.status_code == 200:
            token = resp.json().get("access_token")
    except Exception as e:
        print(f"Request failed: {e}")

    if not token:
        print("Could not obtain access token. Aborting further tests.")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {token}"}

    # 4. POST /api/ingest/text
    print("\n--- [POST] /api/ingest/text ---")
    try:
        resp = httpx.post(
            f"{BASE_URL}/api/ingest/text",
            headers=headers,
            json={"text": "This is a simple raw requirement text for a banking app."},
            timeout=60.0
        )
        print(f"Status: {resp.status_code}")
        print(f"Body: {resp.text}")
    except Exception as e:
        print(f"Request failed: {e}")

    # 5. POST /api/ingest/csv
    print("\n--- [POST] /api/ingest/csv ---")
    csv_file = "test_data.csv"
    with open(csv_file, "w") as f:
        f.write("id,domain,subdomain,raw_requirement\n")
        f.write("1,Ecommerce,Checkout,Checkout should accept Paypal and Apple Pay.\n")
    try:
        with open(csv_file, "rb") as f:
            resp = httpx.post(
                f"{BASE_URL}/api/ingest/csv",
                headers=headers,
                files={"file": (csv_file, f, "text/csv")},
                timeout=60.0
            )
            print(f"Status: {resp.status_code}")
            print(f"Body: {resp.text}")
    except Exception as e:
        print(f"Request failed: {e}")
    finally:
        if os.path.exists(csv_file):
            os.remove(csv_file)

    # 6. POST /api/ingest/json
    print("\n--- [POST] /api/ingest/json ---")
    json_file = "test_data.json"
    requirement_data = [
        {
            "id": 999,
            "domain": "Ecommerce",
            "subdomain": "Payment Gateway",
            "raw_requirement": "Need Stripe integration with credit card validation.",
            "ambiguities": ["Payment frequency and refund rules are not defined."],
            "clarification_questions": ["What is the refund policy for failed payments?"],
            "user_clarifications": ["Refunds should be processed automatically within 3 business days."],
            "refined_summary": "Stripe integration handling auto-refunds in 3 days."
        }
    ]
    with open(json_file, "w") as f:
        json.dump(requirement_data, f)
    try:
        with open(json_file, "rb") as f:
            resp = httpx.post(
                f"{BASE_URL}/api/ingest/json",
                headers=headers,
                files={"file": (json_file, f, "application/json")},
                timeout=60.0
            )
            print(f"Status: {resp.status_code}")
            print(f"Body: {resp.text}")
    except Exception as e:
        print(f"Request failed: {e}")
    finally:
        if os.path.exists(json_file):
            os.remove(json_file)

    # 7. POST /api/ingest/pdf
    print("\n--- [POST] /api/ingest/pdf ---")
    pdf_file = "test_data.pdf"
    generate_minimal_pdf(pdf_file)
    try:
        with open(pdf_file, "rb") as f:
            resp = httpx.post(
                f"{BASE_URL}/api/ingest/pdf",
                headers=headers,
                files={"file": (pdf_file, f, "application/pdf")},
                timeout=60.0
            )
            print(f"Status: {resp.status_code}")
            print(f"Body: {resp.text}")
    except Exception as e:
        print(f"Request failed: {e}")
    finally:
        if os.path.exists(pdf_file):
            os.remove(pdf_file)

    # 8. POST /api/chat/query
    print("\n--- [POST] /api/chat/query ---")
    query_payload = {
        "question": "Need a secure payment gateway integration with Stripe support.",
        "domain": "Ecommerce",
        "session_id": "test_session_123",
        "privacy_mode": False
    }
    try:
        resp = httpx.post(
            f"{BASE_URL}/api/chat/query",
            headers=headers,
            json=query_payload,
            timeout=60.0
        )
        print(f"Status: {resp.status_code}")
        try:
            res_json = resp.json()
            print("Response contains valid JSON:")
            print(json.dumps(res_json, indent=2))
        except Exception:
            print("Response body is not JSON:")
            print(resp.text)
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    run_tests()
