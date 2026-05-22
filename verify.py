import httpx
import json
import sys

def verify_pipeline():
    base_url = "http://127.0.0.1:8000"
    
    # Credentials for a verification test account
    email = "terminal_verification@t.com"
    password = "password"
    
    print("--- 1. REGISTERING VERIFICATION USER ---")
    reg_url = f"{base_url}/auth/register?email={email}&password={password}"
    try:
        reg_resp = httpx.post(reg_url, timeout=10.0)
        print(f"Register status: {reg_resp.status_code}")
        print(f"Register response: {reg_resp.text}\n")
    except Exception as e:
        print(f"Register attempt skipped (User might already exist): {e}\n")
        
    print("--- 2. LOGGING IN ---")
    try:
        login_resp = httpx.post(
            f"{base_url}/auth/login",
            data={"username": email, "password": password},
            timeout=10.0
        )
        print(f"Login status: {login_resp.status_code}")
        token_data = login_resp.json()
        if "access_token" not in token_data:
            print("Failed to login. Please verify uvicorn backend is running.")
            sys.exit(1)
        token = token_data["access_token"]
        print("Successfully obtained access token.\n")
    except Exception as e:
        print(f"Failed to log in: {e}")
        print("Make sure your FastAPI server is running with 'uvicorn main:app --reload'")
        sys.exit(1)
        
    headers = {"Authorization": f"Bearer {token}"}
    
    print("--- 3. INGESTING REQUIREMENTS TEMPLATES ---")
    try:
        with open("data.json", "rb") as f:
            files = {"file": ("data.json", f, "application/json")}
            ingest_resp = httpx.post(
                f"{base_url}/api/ingest/json",
                headers=headers,
                files=files,
                timeout=60.0
            )
        print(f"Ingest status: {ingest_resp.status_code}")
        print(f"Ingest response: {ingest_resp.text}\n")
    except Exception as e:
        print(f"Failed to ingest: {e}\n")
        sys.exit(1)
        
    print("--- 4. QUERYING PIPELINE (ECOMMERCE DOMAIN) ---")
    query_payload = {
        "question": "Need a secure payment gateway integration with Stripe support.",
        "domain": "Ecommerce",
        "session_id": "verify_session",
        "privacy_mode": False
    }
    
    try:
        query_resp = httpx.post(
            f"{base_url}/api/chat/query",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=query_payload,
            timeout=60.0
        )
        print(f"Query status: {query_resp.status_code}")
        result = query_resp.json()
        print("\n--- LLM ANSWER ---")
        print(result.get("answer", "No answer found"))
        print("\n--- RETRIEVED SOURCES ---")
        for source in result.get("sources", []):
            print(f"- Domain: {source.get('domain')}, Subdomain: {source.get('subdomain')}, Req ID: {source.get('requirement_id')}")
        print("\nPipeline verification completed successfully!")
    except Exception as e:
        print(f"Query request failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    verify_pipeline()
