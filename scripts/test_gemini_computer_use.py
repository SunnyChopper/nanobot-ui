#!/usr/bin/env python3
"""Test Gemini API generateContent with and without computer_use tool. Uses GEMINI_API_KEY."""
import os
import json
import urllib.request
import urllib.error

API_KEY = os.environ.get("GEMINI_API_KEY", "")
if not API_KEY:
    print("Set GEMINI_API_KEY")
    exit(1)

BASE = "https://generativelanguage.googleapis.com/v1beta"
MODEL = "gemini-3-flash-preview"

def request(path_suffix: str, body: dict) -> None:
    url = f"{BASE}/{path_suffix}?key={API_KEY}"
    if path_suffix.startswith("models/"):
        url = f"{BASE}/{path_suffix}?key={API_KEY}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print("Status:", r.status)
            out = r.read().decode()
            if len(out) > 500:
                out = out[:500] + "..."
            print("Response:", out[:800])
    except urllib.error.HTTPError as e:
        print("HTTPError:", e.code, e.reason)
        print("Body:", e.read().decode()[:1000])
    except Exception as e:
        print("Error:", type(e).__name__, e)

print("=== 1. Text-only (no tools) ===")
request(f"models/{MODEL}:generateContent", {
    "contents": [{"parts": [{"text": "Say hello in one word"}]}],
})
print()

print("=== 2. With tools: computerUse (camelCase) ENVIRONMENT_BROWSER ===")
request(f"models/{MODEL}:generateContent", {
    "contents": [{"parts": [{"text": "Say hello"}]}],
    "tools": [{"computerUse": {"environment": "ENVIRONMENT_BROWSER"}}],
})
print()

print("=== 3. With tools: computer_use (snake_case) ===")
request(f"models/{MODEL}:generateContent", {
    "contents": [{"parts": [{"text": "Say hello"}]}],
    "tools": [{"computer_use": {"environment": "ENVIRONMENT_BROWSER"}}],
})
