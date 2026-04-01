"""Shared Orion Streamlit dark/glass CSS."""

ORION_STYLE_MARKDOWN = """
<style>
  :root {
    --orion-bg: #05030a;
    --orion-text: rgba(255, 255, 255, 0.98);
    --orion-muted: rgba(255, 255, 255, 0.72);
    --orion-glass: rgba(255, 255, 255, 0.07);
    --orion-border: rgba(190, 170, 255, 0.28);
    --orion-accent: rgba(140, 90, 255, 0.65);
  }

  html, body, [class*="stApp"] {
    background-color: var(--orion-bg) !important;
    color: var(--orion-text) !important;
    background-image:
      radial-gradient(circle at 50% -10%, rgba(140, 90, 255, 0.45), rgba(0,0,0,0) 55%),
      radial-gradient(circle at 15% 85%, rgba(16, 125, 255, 0.30), rgba(0,0,0,0) 55%),
      radial-gradient(circle at 90% 20%, rgba(255, 60, 220, 0.18), rgba(0,0,0,0) 60%);
    background-attachment: fixed;
  }

  .stApp {
    padding-top: 72px;
  }

  div[data-testid="stChatInput"] {
    max-width: 820px;
    margin-left: auto;
    margin-right: auto;
  }

  div[data-testid="stChatInput"] {
    padding: 10px 10px 8px 10px;
    border-radius: 22px;
    border: 1px solid rgba(255,255,255,0.12);
    background: rgba(255,255,255,0.02);
    box-shadow: 0 18px 55px rgba(0, 0, 0, 0.35);
  }

  div[data-testid="stChatInput"] textarea {
    background: rgba(140, 90, 255, 0.08) !important;
    border: 1px solid rgba(190, 170, 255, 0.35) !important;
    color: var(--orion-text) !important;
    border-radius: 18px !important;
    padding: 14px 16px !important;
    backdrop-filter: blur(12px) !important;
    -webkit-backdrop-filter: blur(12px) !important;
    box-shadow:
      inset 0 0 0 1px rgba(255,255,255,0.06),
      0 10px 30px rgba(0,0,0,0.25) !important;
  }

  div[data-testid="stChatInput"] textarea::placeholder {
    color: rgba(255, 255, 255, 0.55) !important;
  }

  div[data-testid="stChatInput"] button {
    color: var(--orion-text) !important;
  }

  .stButton > button {
    background: rgba(255, 255, 255, 0.06) !important;
    border: 1px solid rgba(255, 255, 255, 0.18) !important;
    color: var(--orion-text) !important;
    border-radius: 999px !important;
    padding: 10px 14px !important;
    font-weight: 600 !important;
    backdrop-filter: blur(10px) !important;
    -webkit-backdrop-filter: blur(10px) !important;
  }
  .stButton > button:hover {
    background: rgba(255, 255, 255, 0.10) !important;
    border-color: rgba(255, 255, 255, 0.28) !important;
  }

  .stMarkdown, .stText, .stCaption {
    color: var(--orion-text) !important;
  }

  .stCaption {
    color: var(--orion-muted) !important;
  }

  div[data-testid="stVerticalBlock"],
  div.block-container,
  div[data-testid="stAppViewContainer"],
  section,
  main {
    background: transparent !important;
  }

  div[data-testid="stChatMessage"],
  div[data-testid="stChatMessageContainer"],
  div[data-testid="stChat"] {
    background: transparent !important;
  }
</style>
"""
