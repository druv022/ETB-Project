"""Shared Orion Streamlit CSS."""

ORION_STYLE_MARKDOWN = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

  :root {
    --orion-bg: #070412;
    --orion-bg-soft: #0f0b28;
    --orion-text: rgba(255, 255, 255, 0.98);
    --orion-muted: rgba(219, 210, 250, 0.72);
    --orion-border: rgba(183, 163, 247, 0.30);
    --orion-accent: rgba(140, 90, 255, 0.22);
    --orion-assistant-card: rgba(29, 20, 56, 0.82);
    --orion-user-card: rgba(66, 36, 118, 0.90);
    --orion-sidebar-width: 17.5rem;
  }

  html,
  body,
  [class*="stApp"],
  [class*="stAppViewContainer"] {
    font-family: 'Inter', system-ui, -apple-system, Segoe UI, Roboto, sans-serif !important;
    background-color: var(--orion-bg) !important;
    color: var(--orion-text) !important;
    background-image:
      radial-gradient(circle at 50% -10%, rgba(140, 90, 255, 0.36), rgba(0,0,0,0) 56%),
      radial-gradient(circle at 15% 85%, rgba(16, 125, 255, 0.20), rgba(0,0,0,0) 58%),
      radial-gradient(circle at 90% 20%, rgba(255, 60, 220, 0.12), rgba(0,0,0,0) 60%),
      linear-gradient(180deg, var(--orion-bg-soft) 0%, var(--orion-bg) 100%);
    background-attachment: fixed;
  }

  .stApp {
    padding-top: 0 !important;
  }

  .stMarkdown, .stText, .stCaption, p, label, h1, h2, h3, h4, h5, h6 {
    font-family: 'Inter', system-ui, -apple-system, Segoe UI, Roboto, sans-serif !important;
    font-weight: 500 !important;
  }

  /* Keep Streamlit material icons rendering as icons, not text glyph names. */
  span.material-symbols-rounded,
  span.material-symbols-outlined,
  [class*="material-symbols"],
  [data-testid="stExpanderToggleIcon"] span {
    font-family: 'Material Symbols Rounded' !important;
    font-weight: normal !important;
    font-style: normal !important;
    letter-spacing: normal !important;
    text-transform: none !important;
    white-space: nowrap !important;
    word-wrap: normal !important;
    direction: ltr !important;
    -webkit-font-smoothing: antialiased !important;
  }

  h1 {
    font-size: clamp(2.0rem, 4.2vw, 2.6rem) !important;
    font-weight: 600 !important;
    letter-spacing: -0.02em !important;
  }

  p, .stCaption, .stMarkdown {
    font-size: 0.99rem !important;
    line-height: 1.55 !important;
  }

  div.block-container {
    padding-bottom: 8.25rem !important;
  }

  .stSidebar {
    background: rgba(10, 7, 26, 0.92) !important;
    border-right: 1px solid rgba(183, 163, 247, 0.16) !important;
  }

  .stSidebar .stMarkdown, .stSidebar .stCaption {
    font-size: 0.95rem !important;
  }

  .stSidebar [data-testid="stRadio"] [role="radiogroup"] {
    gap: 0.2rem;
  }

  .stSidebar [data-testid="stRadio"] [role="radiogroup"] label {
    border-radius: 10px !important;
    padding: 0.42rem 0.60rem !important;
    border: 1px solid transparent !important;
    background: transparent !important;
    transition: background-color 120ms ease, border-color 120ms ease !important;
  }

  .stSidebar [data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) {
    background: var(--orion-accent) !important;
    border-color: rgba(183, 163, 247, 0.50) !important;
  }

  .stSidebar [data-testid="stRadio"] [role="radiogroup"] label:hover {
    background: rgba(255, 255, 255, 0.04) !important;
  }

  div[data-testid="stChatMessage"] {
    margin: 0.78rem 0 !important;
  }

  div[data-testid="stChatMessage"] div[data-testid="stChatMessageContent"] {
    border-radius: 12px !important;
    border: 1px solid var(--orion-border) !important;
    background: var(--orion-assistant-card) !important;
    padding: 0.82rem 0.95rem !important;
    max-width: min(82%, 820px);
  }

  div[data-testid="stChatMessage"]:has([data-testid*="UserAvatar"]) {
    justify-content: flex-end !important;
    text-align: left !important;
  }

  div[data-testid="stChatMessage"]:has([data-testid*="UserAvatar"]) div[data-testid="stChatMessageContent"] {
    background: var(--orion-user-card) !important;
    border-color: rgba(209, 191, 255, 0.38) !important;
  }

  div[data-testid="stChatMessage"]:has([data-testid*="AssistantAvatar"]) {
    justify-content: flex-start !important;
  }

  [data-testid="stExpander"] {
    border: 1px solid var(--orion-border) !important;
    border-radius: 12px !important;
    background: rgba(18, 12, 38, 0.70) !important;
    overflow: hidden !important;
  }

  [data-testid="stExpander"] summary {
    font-size: 0.98rem !important;
    font-weight: 500 !important;
    padding: 0.78rem 1rem !important;
    border-bottom: 1px solid rgba(183, 163, 247, 0.20) !important;
    min-height: auto !important;
    line-height: 1.35 !important;
  }

  [data-testid="stExpander"] summary p,
  [data-testid="stExpander"] summary span {
    margin: 0 !important;
    line-height: 1.35 !important;
  }

  [data-testid="stExpander"] [data-testid="stMarkdownContainer"] {
    padding-top: 0.45rem !important;
  }

  div[data-testid="stChatInput"] button {
    color: var(--orion-text) !important;
  }

  div[data-testid="stChatInput"] {
    position: fixed;
    left: max(1rem, env(safe-area-inset-left, 0px) + 0.5rem);
    right: max(1rem, env(safe-area-inset-right, 0px) + 0.5rem);
    bottom: max(1rem, env(safe-area-inset-bottom, 0px) + 0.25rem);
    z-index: 999;
    max-width: min(1040px, calc(100vw - 2rem));
    margin: 0 auto !important;
    padding: 0.55rem !important;
    border-radius: 14px;
    border: 1px solid rgba(183, 163, 247, 0.32);
    background: rgba(15, 10, 33, 0.92) !important;
    box-shadow: 0 14px 36px rgba(0, 0, 0, 0.42);
  }

  /*
   * Desktop: keep fixed chat input clear of the left sidebar.
   * Main content already flows correctly; fixed bars need explicit offset.
   */
  @media (min-width: 769px) {
    div.block-container {
      padding-left: 1.8rem !important;
      padding-right: 1.8rem !important;
    }

    div[data-testid="stChatInput"] {
      left: calc(var(--orion-sidebar-width) + 1.1rem) !important;
      right: 1.1rem !important;
      max-width: none !important;
      margin: 0 !important;
    }
  }

  div[data-testid="stChatInput"] textarea {
    background: rgba(255,255,255,0.02) !important;
    border: 1px solid rgba(183, 163, 247, 0.36) !important;
    color: var(--orion-text) !important;
    border-radius: 10px !important;
    min-height: 2.9rem !important;
    padding: 0.95rem 1.05rem !important;
    box-shadow: none !important;
  }

  div[data-testid="stChatInput"] textarea::placeholder {
    color: rgba(219, 210, 250, 0.58) !important;
  }

  .stButton > button {
    background: rgba(255, 255, 255, 0.05) !important;
    border: 1px solid rgba(183, 163, 247, 0.30) !important;
    color: var(--orion-text) !important;
    border-radius: 10px !important;
    padding: 0.48rem 0.72rem !important;
    font-weight: 500 !important;
  }

  .stButton > button:hover {
    background: rgba(140, 90, 255, 0.16) !important;
    border-color: rgba(183, 163, 247, 0.45) !important;
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
