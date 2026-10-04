import os
import re
from google import genai
from google.genai import types

# 1. Initialize Gemini Client
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY environment variable is missing.")

client = genai.Client(api_key=api_key)

# 2. Dynamic Model Selection Function
def get_best_lite_model(client: genai.Client) -> str:
    """Queries available models dynamically and picks the newest active lite/flash model."""
    try:
        lite_models = []
        for model in client.models.list():
            name = model.name.lower()
            # Look for flash or lite models
            if "flash" in name or "lite" in name:
                lite_models.append(model.name)
        
        if lite_models:
            lite_models.sort()
            # Extract clean model string (e.g., 'models/gemini-3.8-flash' -> 'gemini-3.8-flash')
            return lite_models[-1].replace("models/", "")
    except Exception as e:
        print(f"Dynamic model lookup warning: {e}. Falling back to default.")
    
    return "gemini-3.8-flash"

selected_model = get_best_lite_model(client)
print(f"Using dynamically selected model: {selected_model}")

# 3. Native App Curation Prompt
prompt = """
You are an expert native software curation agent.
Search Product Hunt, Show HN, GitHub, and Reddit for native application launches for macOS, Windows, and iPadOS from the past week.

CRITICAL FILTERS:
1. EXCLUDE all "vibe-coded" Electron web wrappers, single-prompt ChatGPT API skins, landing page prototypes, and simple web bookmarklets.
2. INCLUDE ONLY genuine native engineering (e.g., Swift, SwiftUI, C++, Rust, WinUI 3, Metal, Vulkan, native OS menu bar/system integration).

For 3 to 5 verified apps found, generate a clean HTML string.
Each app MUST use this exact HTML structure:

<div class="app-card">
  <div class="card-header">
    <h3>App Name</h3>
    <span class="platform-badge macos">macOS</span> <!-- Use macos, windows, or ipados -->
  </div>
  <p><a href="URL_HERE" target="_blank">View Release / Source</a></p>
  <p>2-sentence description of what the app does and why it stands out.</p>
  <span class="quality-tag">Native Tech Stack (e.g., Swift / Menu Bar Utility)</span>
</div>

Return ONLY valid HTML elements inside a single <div> wrapper. Do not wrap in markdown code blocks like ```html.
"""

# 4. Generate Content using the Dynamic Model
response = client.models.generate_content(
    model=selected_model,
    contents=prompt,
    config=types.GenerateContentConfig(
        tools=[{"google_search": {}}],
    ),
)

new_content = response.text.strip()

# Clean up markdown code blocks if present
new_content = re.sub(r"^```html\s*", "", new_content)
new_content = re.sub(r"\s*```$", "", new_content)

# Append to dashboard.html
with open("dashboard.html", "a", encoding="utf-8") as f:
    f.write("\n\n" + new_content)

print("Successfully appended new native app entries to dashboard.html")
