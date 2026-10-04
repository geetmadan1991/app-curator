import os
import re
import csv
import json
from google import genai
from google.genai import types

# 1. Initialize Gemini Client
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY environment variable is missing.")

client = genai.Client(api_key=api_key)

# Load previously seen apps from CSV
CSV_FILE = "seen_apps.csv"
seen_apps = set()

if os.path.exists(CSV_FILE):
    with open(CSV_FILE, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if row:
                seen_apps.add(row[0].strip().lower())

print(f"Loaded {len(seen_apps)} previously processed apps from history.")

# 2. Select active model
def get_active_model(client: genai.Client) -> str:
    priority_models = ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.5-flash"]
    try:
        available = [m.name.replace("models/", "") for m in client.models.list()]
        for target in priority_models:
            if target in available:
                return target
    except Exception as e:
        print(f"Model listing notice: {e}")
    return "gemini-3.5-flash-lite"

selected_model = get_active_model(client)

# 3. Prompt requesting structured evaluation + HTML output
prompt = f"""
You are an expert native software curation agent.
Search Product Hunt, Show HN, GitHub, and Reddit for native application launches for macOS, Windows, and iPadOS from the past week.

DO NOT evaluate these previously processed apps: {list(seen_apps)}

EVALUATION CRITERIA:
- REJECT: Electron web wrappers, single-prompt ChatGPT skins, web apps, bookmarklets.
- ACCEPT: Native tech stacks (Swift, C++, Rust, WinUI 3, Metal, Vulkan, native system integration).

Return a valid JSON object matching this schema:
{{
  "accepted_apps": [
    {{
      "name": "App Name",
      "platform": "macOS",
      "url": "https://...",
      "description": "2-sentence summary",
      "tech_stack": "Swift / Menu Bar",
      "html_card": "<div class=\\"app-card\\">...</div>"
    }}
  ],
  "rejected_apps": [
    {{
      "name": "Rejected App Name",
      "reason": "Electron wrapper / Web skin"
    }}
  ]
}}
"""

response = client.models.generate_content(
    model=selected_model,
    contents=prompt,
    config=types.GenerateContentConfig(
        tools=[{"google_search": {}}],
        response_mime_type="application/json"
    ),
)

data = json.loads(response.text)

# Append results to seen_apps.csv
with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    
    for app in data.get("accepted_apps", []):
        writer.writerow([app["name"], "ACCEPTED", app.get("tech_stack", "Native")])
        
        # Append HTML to dashboard
        with open("dashboard.html", "a", encoding="utf-8") as dash:
            dash.write("\n\n" + app["html_card"])
            
    for app in data.get("rejected_apps", []):
        writer.writerow([app["name"], "REJECTED", app.get("reason", "Non-native")])

print(f"Logged {len(data.get('accepted_apps', []))} accepted and {len(data.get('rejected_apps', []))} rejected apps to {CSV_FILE}.")
