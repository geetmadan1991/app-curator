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

# 2. Load historical apps from CSV to prevent repeating
CSV_FILE = "seen_apps.csv"
seen_apps = set()

if os.path.exists(CSV_FILE):
    with open(CSV_FILE, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if row:
                seen_apps.add(row[0].strip().lower())

print(f"Loaded {len(seen_apps)} previously processed apps from history.")

# 3. Select active model
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
print(f"Executing curation with model: {selected_model}")

# 4. Curation Prompt
prompt = f"""
You are an expert native software curation agent.
Search Product Hunt, Show HN, GitHub, and Reddit for native application launches for macOS, Windows, and iPadOS from the past week.

DO NOT evaluate these previously processed apps: {list(seen_apps)}

CRITICAL FILTERS:
1. EXCLUDE all "vibe-coded" Electron web wrappers, single-prompt ChatGPT API skins, landing page prototypes, and web bookmarklets.
2. INCLUDE ONLY genuine native engineering (Swift, SwiftUI, C++, Rust, WinUI 3, Metal, Vulkan).

Output your results as a JSON block wrapped in ```json ... ``` with two keys:
1. "accepted": list of objects with "name", "platform", "url", "description", "tech_stack", and "html_card".
2. "rejected": list of objects with "name" and "reason".

Each "html_card" inside "accepted" MUST use this exact HTML structure:
<div class="app-card">
  <div class="card-header">
    <h3>App Name</h3>
    <span class="platform-badge macos">macOS</span>
  </div>
  <p><a href="URL_HERE" target="_blank">View Release / Source</a></p>
  <p>2-sentence description of what the app does and why it stands out.</p>
  <span class="quality-tag">Native Tech Stack</span>
</div>
"""

# 5. Generate Content using Search Tool
response = client.models.generate_content(
    model=selected_model,
    contents=prompt,
    config=types.GenerateContentConfig(
        tools=[{"google_search": {}}],
    ),
)

raw_text = response.text or ""

# Extract JSON string from markdown code blocks
json_match = re.search(r"```json\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
if json_match:
    json_str = json_match.group(1)
else:
    # Fallback to general curly brace matching if markdown code fence is missing
    json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    json_str = json_match.group(0) if json_match else "{}"

try:
    data = json.loads(json_str)
except Exception as e:
    print(f"Failed to parse JSON: {e}\nRaw Output was:\n{raw_text}")
    data = {"accepted": [], "rejected": []}

accepted_apps = data.get("accepted", [])
rejected_apps = data.get("rejected", [])

# 6. Save results to CSV and dashboard.html
file_exists = os.path.exists(CSV_FILE)
with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    if not file_exists:
        writer.writerow(["App Name", "Status", "Details"])
    
    for app in accepted_apps:
        writer.writerow([app.get("name", "Unknown"), "ACCEPTED", app.get("tech_stack", "Native")])
        if "html_card" in app:
            with open("dashboard.html", "a", encoding="utf-8") as dash:
                dash.write("\n\n" + app["html_card"])
                
    for app in rejected_apps:
        writer.writerow([app.get("name", "Unknown"), "REJECTED", app.get("reason", "Non-native")])

print(f"Processed {len(accepted_apps)} accepted and {len(rejected_apps)} rejected apps.")
