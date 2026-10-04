import os
import re
from google import genai
from google.genai import types

# Initialize Gemini Client using the hidden GitHub Secret
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY environment variable is missing.")

client = genai.Client(api_key=api_key)

# The curation instructions enforcing native app standards
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

print("Executing Gemini 2.5 search grounding and curation...")

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt,
    config=types.GenerateContentConfig(
        tools=[{"google_search": {}}],
    ),
)

new_content = response.text.strip()

# Clean up markdown code block ticks if the model returns them
new_content = re.sub(r"^```html\s*", "", new_content)
new_content = re.sub(r"\s*```$", "", new_content)

# Append the newly generated app cards into dashboard.html
with open("dashboard.html", "a", encoding="utf-8") as f:
    f.write("\n\n" + new_content)

print("Successfully appended new native app entries to dashboard.html")
