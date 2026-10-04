import os
import re
import csv
import json
import genai
from google.genai import types

# 1. Initialize Gemini Client
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY environment variable is missing.")

client = genai.Client(api_key=api_key)

# 2. Read previously processed apps from CSV
CSV_FILE = "seen_apps.csv"
seen_apps = set()

if os.path.exists(CSV_FILE):
    with open(CSV_FILE, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if row:
                seen_apps.add(row[0].strip().lower())

print(f"Loaded {len(seen_apps)} historical apps from CSV.")

# 3. Model Selector
def get_active_model(client: genai.Client) -> str:
    priority = ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.5-flash"]
    try:
        available = [m.name.replace("models/", "") for m in client.models.list()]
        for target in priority:
            if target in available:
                return target
    except Exception as e:
        print(f"Model lookup fallback: {e}")
    return "gemini-3.5-flash-lite"

selected_model = get_active_model(client)
print(f"Using model: {selected_model}")

# 4. Multi-Platform Prompting Strategy
prompt = f"""
You are an expert native software curation agent.
Search Product Hunt, GitHub Releases, Show HN, and Reddit for native desktop/tablet app launches from the past week.

DO NOT process these previously evaluated apps: {list(seen_apps)}

PLATFORM MANDATE:
You MUST return a balanced set of native apps covering ALL THREE platforms:
1. At least 1 macOS app (Swift / SwiftUI / Metal)
2. At least 1 Windows app (WinUI 3 / C# / Rust / C++)
3. At least 1 iPadOS app (SwiftUI / PencilKit)

EXCLUDE: All Electron, Tauri, Web-wrapper, or simple API skins.

Return a valid JSON code block wrapped in ```json ... ``` with two root keys:
"accepted" and "rejected".

Each object in "accepted" MUST have:
- "name": string
- "platform": "macOS" | "Windows" | "iPadOS"
- "category": "dev" (for Developer/System) OR "prod" (for Productivity/Creative)
- "url": string
- "image_url": "https://..." (Direct URL to project screenshot, logo, or open-graph banner image. Fallback to a relevant Unsplash tech image URL if none found)
- "description": "2 concise sentences explaining functionality."
- "tech_stack": e.g. "Rust / WinUI 3" or "SwiftUI / Metal"

Each object in "rejected" MUST have:
- "name": string
- "reason": string
"""

response = client.models.generate_content(
    model=selected_model,
    contents=prompt,
    config=types.GenerateContentConfig(
        tools=[{"google_search": {}}],
    ),
)

raw_text = response.text or ""

# Extract JSON response block
json_match = re.search(r"```json\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
if json_match:
    json_str = json_match.group(1)
else:
    json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    json_str = json_match.group(0) if json_match else "{}"

try:
    data = json.loads(json_str)
except Exception as e:
    print(f"JSON Parse Error: {e}\nRaw response:\n{raw_text}")
    data = {"accepted": [], "rejected": []}

accepted_apps = data.get("accepted", [])
rejected_apps = data.get("rejected", [])

# 5. Inject Cards into dashboard.html & append CSV
if os.path.exists("dashboard.html"):
    with open("dashboard.html", "r", encoding="utf-8") as f:
        html_content = f.read()

    for app in accepted_apps:
        platform_class = app.get("platform", "macOS").lower()
        image_src = app.get("image_url", "https://images.unsplash.com/photo-1518770660439-4636190af475?w=600&auto=format&fit=crop")
        
        card_html = f"""
        <div class="app-card">
          <img class="app-media" src="{image_src}" alt="{app.get('name')} screenshot" onerror="this.src='https://images.unsplash.com/photo-1518770660439-4636190af475?w=600&auto=format&fit=crop';">
          <div class="app-body">
            <div class="card-header">
              <span class="app-title">{app.get('name')}</span>
              <span class="badge {platform_class}">{app.get('platform')}</span>
            </div>
            <p class="description">{app.get('description')}</p>
            <div class="card-footer">
              <span class="tech-tag">{app.get('tech_stack', 'Native')}</span>
              <a href="{app.get('url')}" target="_blank" class="source-link">View Project →</a>
            </div>
          </div>
        </div>
        """
        
        # Inject into Developer or Productivity grid target
        target_grid_id = 'id="dev-grid">' if app.get("category") == "dev" else 'id="prod-grid">'
        if target_grid_id in html_content:
            html_content = html_content.replace(target_grid_id, target_grid_id + "\n" + card_html)

    with open("dashboard.html", "w", encoding="utf-8") as f:
        f.write(html_content)

# Update CSV Log
file_exists = os.path.exists(CSV_FILE)
with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    if not file_exists:
        writer.writerow(["App Name", "Status", "Details"])
    
    for app in accepted_apps:
        writer.writerow([app.get("name"), "ACCEPTED", app.get("tech_stack")])
    for app in rejected_apps:
        writer.writerow([app.get("name"), "REJECTED", app.get("reason")])

print(f"Successfully processed {len(accepted_apps)} multi-platform native apps.")
