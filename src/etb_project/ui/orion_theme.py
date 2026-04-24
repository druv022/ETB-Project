"""Shared Orion Streamlit CSS."""

ORION_STYLE_MARKDOWN = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

  :root {
    --orion-bg: #070412;
    --orion-bg-soft: #0b0918;
    --orion-text: rgba(255, 255, 255, 0.98);
    --orion-muted: rgba(219, 210, 250, 0.72);
    --orion-border: rgba(216, 216, 224, 0.20);
    --orion-accent: rgba(255, 255, 255, 0.08);
    --orion-assistant-card: rgba(0, 0, 0, 0.42);
    --orion-user-card: rgba(13, 13, 18, 0.62);
    --orion-sidebar-width: 17.5rem;
  }

  html,
  body,
  [class*="stApp"],
  [class*="stAppViewContainer"] {
    font-family: 'Inter', system-ui, -apple-system, Segoe UI, Roboto, sans-serif !important;
    background-color: #0a0520 !important;
    color: var(--orion-text) !important;
    background-image:
      linear-gradient(120deg, rgba(26, 16, 77, 0.98) 0%, rgba(58, 22, 105, 0.92) 100%);
    background-attachment: fixed;
    background-size: cover;
    background-position: center;
  }

  [data-testid="stAppViewContainer"] {
    position: relative;
    isolation: isolate;
    overflow-x: hidden;
    overflow-y: auto;
  }

  /* Shader-like plasma/grid background layers. */
  [data-testid="stAppViewContainer"]::before,
  [data-testid="stAppViewContainer"]::after {
    content: "";
    position: fixed;
    inset: 0;
    pointer-events: none;
    z-index: -1;
    background-position: center;
    background-size: cover;
    background-repeat: no-repeat;
  }

  /* Base grid — major + minor lines, with vertical fade overlay. */
  [data-testid="stAppViewContainer"]::before {
    background-image:
      linear-gradient(rgba(180, 130, 255, 0.10) 1px, transparent 1px),
      linear-gradient(90deg, rgba(180, 130, 255, 0.10) 1px, transparent 1px),
      linear-gradient(rgba(150, 100, 230, 0.22) 1px, transparent 1px),
      linear-gradient(90deg, rgba(150, 100, 230, 0.22) 1px, transparent 1px),
      radial-gradient(ellipse at 50% 0%, rgba(102, 51, 204, 0.35), rgba(0,0,0,0) 62%),
      radial-gradient(ellipse at 50% 100%, rgba(23, 12, 54, 0.85), rgba(0,0,0,0) 58%);
    background-size:
      34px 34px,
      34px 34px,
      170px 170px,
      170px 170px,
      100% 100%,
      100% 100%;
    opacity: 0.9;
    animation: orion-grid-drift 40s linear infinite;
  }

  /* Animated plasma waves — purple streaks drifting horizontally. */
  [data-testid="stAppViewContainer"]::after {
    background-image:
      radial-gradient(ellipse 60% 18% at 20% 42%, rgba(140, 70, 255, 0.45), transparent 70%),
      radial-gradient(ellipse 70% 14% at 75% 58%, rgba(170, 90, 255, 0.40), transparent 70%),
      radial-gradient(ellipse 55% 12% at 50% 30%, rgba(100, 60, 220, 0.38), transparent 70%),
      radial-gradient(ellipse 50% 10% at 30% 78%, rgba(180, 110, 255, 0.30), transparent 70%);
    filter: blur(40px) saturate(120%);
    mix-blend-mode: screen;
    opacity: 0.85;
    animation: orion-plasma-drift 22s ease-in-out infinite alternate;
  }

  @keyframes orion-grid-drift {
    0%   { background-position: 0 0, 0 0, 0 0, 0 0, center, center; }
    100% { background-position: 34px 34px, -34px 34px, 170px 170px, -170px 170px, center, center; }
  }

  @keyframes orion-plasma-drift {
    0% {
      transform: translate3d(-4%, -2%, 0) scale(1.05);
      opacity: 0.75;
    }
    50% {
      transform: translate3d(3%, 2%, 0) scale(1.12);
      opacity: 0.95;
    }
    100% {
      transform: translate3d(5%, -3%, 0) scale(1.08);
      opacity: 0.80;
    }
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
    font-size: clamp(2.2rem, 4.4vw, 2.9rem) !important;
    font-weight: 600 !important;
    letter-spacing: -0.02em !important;
    text-align: center !important;
    margin-top: 1.25rem !important;
  }

  p, .stCaption, .stMarkdown {
    font-size: 0.99rem !important;
    line-height: 1.55 !important;
  }

  div.block-container {
    padding-bottom: 2rem !important;
    max-width: 980px !important;
  }

  .stSidebar,
  [data-testid="stSidebar"] {
    background: transparent !important;
    background-color: transparent !important;
    border-right: 1px solid rgba(236, 236, 244, 0.08) !important;
    backdrop-filter: blur(6px) !important;
  }

  .stSidebar > div,
  [data-testid="stSidebar"] > div,
  [data-testid="stSidebarContent"],
  [data-testid="stSidebarUserContent"] {
    background: transparent !important;
    background-color: transparent !important;
  }

  /* Sidebar toggle: subtle but visible over the background. */
  [data-testid="stSidebarCollapsedControl"],
  [data-testid="stSidebarCollapseButton"] {
    z-index: 100 !important;
  }

  [data-testid="stSidebarCollapsedControl"] button,
  [data-testid="stSidebarCollapseButton"] button,
  button[kind="header"] {
    background: rgba(20, 20, 28, 0.55) !important;
    border: 1px solid rgba(236, 236, 244, 0.18) !important;
    color: var(--orion-text) !important;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.35) !important;
    backdrop-filter: blur(8px) !important;
    border-radius: 10px !important;
  }

  [data-testid="stSidebarCollapsedControl"] button svg,
  [data-testid="stSidebarCollapseButton"] button svg,
  button[kind="header"] svg {
    color: var(--orion-text) !important;
    fill: var(--orion-text) !important;
  }

  [data-testid="stSidebarCollapsedControl"] button:hover,
  [data-testid="stSidebarCollapseButton"] button:hover,
  button[kind="header"]:hover {
    background: rgba(40, 40, 52, 0.75) !important;
    border-color: rgba(236, 236, 244, 0.30) !important;
  }

  .stSidebar .stMarkdown, .stSidebar .stCaption {
    font-size: 0.95rem !important;
  }

  /* --- Modern sidebar: brand mark, user card, logout button --- */
  .orion-sidebar-brand {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    padding: 0.2rem 0.15rem 0.9rem 0.15rem;
    border-bottom: 1px solid rgba(236, 236, 244, 0.08);
    margin-bottom: 0.95rem;
  }
  .orion-sidebar-mark {
    position: relative;
    width: 34px;
    height: 34px;
    flex-shrink: 0;
  }
  .orion-sidebar-orb {
    position: absolute;
    inset: 0;
    border-radius: 50%;
    background:
      radial-gradient(circle at 32% 28%,
        #f5ebff 0%, #b49cff 30%, #6d28d9 65%, #1e1446 100%);
    box-shadow:
      inset -3px -4px 8px rgba(0, 0, 0, 0.55),
      inset 3px 4px 8px rgba(255, 255, 255, 0.20),
      0 4px 14px rgba(139, 92, 246, 0.38),
      0 0 12px rgba(139, 92, 246, 0.28);
  }
  .orion-sidebar-brand-text {
    display: flex;
    flex-direction: column;
    line-height: 1.15;
  }
  .orion-sidebar-brand-title {
    font-size: 1.05rem;
    font-weight: 700;
    letter-spacing: -0.01em;
    background: linear-gradient(180deg, #ffffff 0%, #d8d4ff 100%);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  .orion-sidebar-brand-sub {
    font-size: 0.70rem;
    color: rgba(219, 210, 250, 0.62);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-top: 2px;
  }

  .orion-sidebar-user {
    display: flex;
    align-items: center;
    gap: 0.7rem;
    padding: 0.7rem 0.75rem;
    border-radius: 12px;
    border: 1px solid rgba(236, 236, 244, 0.10);
    background: linear-gradient(
      145deg,
      rgba(255, 255, 255, 0.04) 0%,
      rgba(255, 255, 255, 0.015) 100%
    );
    backdrop-filter: blur(6px);
    margin-bottom: 0.7rem;
  }
  .orion-sidebar-avatar {
    width: 36px;
    height: 36px;
    flex-shrink: 0;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.92rem;
    font-weight: 700;
    color: #ffffff;
    background: linear-gradient(145deg, #a78bfa 0%, #6d28d9 100%);
    border: 1px solid rgba(216, 198, 255, 0.45);
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.22),
      0 4px 10px rgba(109, 40, 217, 0.35);
    letter-spacing: 0.02em;
  }
  .orion-sidebar-user-text {
    min-width: 0;
    display: flex;
    flex-direction: column;
    line-height: 1.2;
  }
  .orion-sidebar-username {
    font-size: 0.92rem;
    font-weight: 600;
    color: #ffffff;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .orion-sidebar-role {
    display: inline-flex;
    align-items: center;
    gap: 0.32rem;
    font-size: 0.70rem;
    font-weight: 500;
    letter-spacing: 0.05em;
    color: rgba(219, 210, 250, 0.78);
    margin-top: 3px;
    text-transform: uppercase;
  }
  .orion-sidebar-role .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #4ade80;
    box-shadow: 0 0 6px #4ade80;
  }
  .orion-sidebar-role-admin .dot {
    background: #fbbf24;
    box-shadow: 0 0 6px #fbbf24;
  }

  /* Logout button styling */
  .stSidebar [data-testid="stButton"] > button {
    background: rgba(255, 255, 255, 0.04) !important;
    border: 1px solid rgba(236, 236, 244, 0.14) !important;
    color: var(--orion-text) !important;
    border-radius: 10px !important;
    padding: 0.52rem 0.8rem !important;
    font-size: 0.87rem !important;
    font-weight: 500 !important;
    transition: background-color 140ms ease, border-color 140ms ease, transform 120ms ease !important;
    margin-bottom: 0.9rem !important;
  }
  .stSidebar [data-testid="stButton"] > button:hover {
    background: rgba(167, 139, 250, 0.16) !important;
    border-color: rgba(183, 163, 247, 0.40) !important;
  }
  .stSidebar [data-testid="stButton"] > button:active {
    transform: translateY(1px);
  }

  /* Section header (the "Section" label over the radio) */
  .stSidebar [data-testid="stWidgetLabel"] p,
  .stSidebar [data-testid="stRadio"] > label p {
    font-size: 0.68rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.10em !important;
    color: rgba(219, 210, 250, 0.50) !important;
    margin-bottom: 0.35rem !important;
  }

  /* Hide the horizontal separator the admin shell draws; the user card already separates */
  .stSidebar hr {
    border: none !important;
    border-top: 1px solid rgba(236, 236, 244, 0.06) !important;
    margin: 0.5rem 0 0.9rem 0 !important;
  }

  .stSidebar [data-testid="stRadio"] [role="radiogroup"] {
    gap: 0.25rem;
    padding: 0 !important;
  }

  /* Base option row: flex with left accent bar reservation */
  .stSidebar [data-testid="stRadio"] [role="radiogroup"] label {
    position: relative !important;
    display: flex !important;
    align-items: center !important;
    gap: 0.65rem !important;
    border-radius: 10px !important;
    padding: 0.58rem 0.75rem 0.58rem 0.85rem !important;
    border: 1px solid transparent !important;
    background: transparent !important;
    transition: background 140ms ease, border-color 140ms ease,
                color 140ms ease, transform 120ms ease !important;
    font-size: 0.93rem !important;
    font-weight: 500 !important;
    color: rgba(228, 224, 246, 0.78) !important;
    cursor: pointer !important;
    overflow: hidden !important;
  }

  /* Hide Streamlit's default radio circle; we render a custom icon instead. */
  .stSidebar [data-testid="stRadio"] [role="radiogroup"] label > div:first-child,
  .stSidebar [data-testid="stRadio"] [role="radiogroup"] label input[type="radio"] {
    display: none !important;
  }

  .stSidebar [data-testid="stRadio"] [role="radiogroup"] label > div {
    display: flex !important;
    align-items: center !important;
    gap: 0.65rem !important;
    flex: 1 1 auto !important;
  }

  /* Icon slot (::before on the label) — uses background-image with inline SVG */
  .stSidebar [data-testid="stRadio"] [role="radiogroup"] label::before {
    content: "";
    display: inline-block;
    width: 18px;
    height: 18px;
    flex-shrink: 0;
    background-repeat: no-repeat;
    background-position: center;
    background-size: contain;
    opacity: 0.72;
    transition: opacity 140ms ease, transform 140ms ease, filter 140ms ease;
  }

  /* Left accent bar (::after), hidden by default, visible on selected */
  .stSidebar [data-testid="stRadio"] [role="radiogroup"] label::after {
    content: "";
    position: absolute;
    left: 0;
    top: 22%;
    bottom: 22%;
    width: 3px;
    border-radius: 0 3px 3px 0;
    background: linear-gradient(180deg, #c4b5fd 0%, #7c3aed 100%);
    opacity: 0;
    transform: scaleY(0.6);
    transition: opacity 160ms ease, transform 160ms ease;
    box-shadow: 0 0 12px rgba(167, 139, 250, 0.65);
  }

  /* Per-section SVG icons (URL-encoded inline SVGs as background-image).
     The stroke color %23dbd2fa = rgb(219,210,250) = our lavender muted tone. */
  .stSidebar [data-testid="stRadio"] [role="radiogroup"] label:has(input[value="Orion"])::before {
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23dbd2fa' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolygon points='12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2'/%3E%3C/svg%3E");
  }

  .stSidebar [data-testid="stRadio"] [role="radiogroup"] label:has(input[value="Logs"])::before {
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23dbd2fa' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z'/%3E%3Cpolyline points='14 2 14 8 20 8'/%3E%3Cline x1='16' y1='13' x2='8' y2='13'/%3E%3Cline x1='16' y1='17' x2='8' y2='17'/%3E%3Cline x1='10' y1='9' x2='8' y2='9'/%3E%3C/svg%3E");
  }

  .stSidebar [data-testid="stRadio"] [role="radiogroup"] label:has(input[value="Settings"])::before {
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23dbd2fa' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='3'/%3E%3Cpath d='M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z'/%3E%3C/svg%3E");
  }

  .stSidebar [data-testid="stRadio"] [role="radiogroup"] label:has(input[value="System health"])::before {
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23dbd2fa' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='22 12 18 12 15 21 9 3 6 12 2 12'/%3E%3C/svg%3E");
  }

  .stSidebar [data-testid="stRadio"] [role="radiogroup"] label:has(input[value="Documents"])::before {
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23dbd2fa' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z'/%3E%3C/svg%3E");
  }

  /* Hover state */
  .stSidebar [data-testid="stRadio"] [role="radiogroup"] label:hover {
    background: rgba(255, 255, 255, 0.045) !important;
    color: rgba(255, 255, 255, 0.92) !important;
    border-color: rgba(236, 236, 244, 0.08) !important;
  }
  .stSidebar [data-testid="stRadio"] [role="radiogroup"] label:hover::before {
    opacity: 1;
    transform: scale(1.05);
  }

  /* Selected (checked) state */
  .stSidebar [data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) {
    background: linear-gradient(
      135deg,
      rgba(167, 139, 250, 0.22) 0%,
      rgba(109, 40, 217, 0.14) 100%
    ) !important;
    border-color: rgba(183, 163, 247, 0.35) !important;
    color: #ffffff !important;
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.08),
      0 4px 14px rgba(109, 40, 217, 0.22) !important;
    font-weight: 600 !important;
  }
  .stSidebar [data-testid="stRadio"] [role="radiogroup"] label:has(input:checked)::before {
    opacity: 1;
    filter: drop-shadow(0 0 6px rgba(167, 139, 250, 0.55));
  }
  .stSidebar [data-testid="stRadio"] [role="radiogroup"] label:has(input:checked)::after {
    opacity: 1;
    transform: scaleY(1);
  }

  div[data-testid="stChatMessage"] {
    margin: 0.9rem 0 !important;
    gap: 0.7rem !important;
    align-items: flex-start !important;
    background: transparent !important;
    padding: 0 !important;
    border: none !important;
  }

  div[data-testid="stChatMessage"] div[data-testid="stChatMessageContent"] {
    border-radius: 16px !important;
    border: 1px solid rgba(216, 216, 232, 0.14) !important;
    background: linear-gradient(
      145deg,
      rgba(22, 14, 50, 0.78) 0%,
      rgba(12, 8, 28, 0.62) 100%
    ) !important;
    backdrop-filter: blur(10px) saturate(1.1) !important;
    -webkit-backdrop-filter: blur(10px) saturate(1.1) !important;
    padding: 0.95rem 1.15rem !important;
    width: fit-content !important;
    max-width: min(76%, 720px) !important;
    flex: 0 1 auto !important;
    box-shadow:
      0 1px 0 rgba(255, 255, 255, 0.04) inset,
      0 8px 24px rgba(0, 0, 0, 0.32) !important;
    font-size: 0.96rem !important;
    line-height: 1.55 !important;
    display: block !important;
    justify-content: flex-start !important;
    align-items: flex-start !important;
    text-align: left !important;
  }

  /* Reset spacing inside the markdown container so text hugs the padding evenly. */
  div[data-testid="stChatMessage"] div[data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"] {
    display: block !important;
    padding: 0 !important;
    margin: 0 !important;
    line-height: 1.55 !important;
  }

  div[data-testid="stChatMessage"] div[data-testid="stChatMessageContent"] p,
  div[data-testid="stChatMessage"] div[data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"] p {
    margin: 0 0 0.5rem 0 !important;
    padding: 0 !important;
    line-height: 1.55 !important;
  }
  div[data-testid="stChatMessage"] div[data-testid="stChatMessageContent"] p:first-child,
  div[data-testid="stChatMessage"] div[data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"] p:first-child {
    margin-top: 0 !important;
  }
  div[data-testid="stChatMessage"] div[data-testid="stChatMessageContent"] p:last-child,
  div[data-testid="stChatMessage"] div[data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"] p:last-child {
    margin-bottom: 0 !important;
  }

  /* USER message: left aligned like a standard chatbot, bright lavender gradient */
  div[data-testid="stChatMessage"]:has([data-testid*="UserAvatar"]) {
    justify-content: flex-start !important;
    text-align: left !important;
    flex-direction: row !important;
  }

  div[data-testid="stChatMessage"]:has([data-testid*="UserAvatar"]) div[data-testid="stChatMessageContent"] {
    background: linear-gradient(
      135deg,
      #8b5cf6 0%,
      #6d28d9 55%,
      #4c1d95 100%
    ) !important;
    border: 1px solid rgba(216, 198, 255, 0.55) !important;
    color: #ffffff !important;
    box-shadow:
      0 1px 0 rgba(255, 255, 255, 0.18) inset,
      0 10px 24px rgba(109, 40, 217, 0.45),
      0 0 0 1px rgba(167, 139, 250, 0.22) !important;
  }
  div[data-testid="stChatMessage"]:has([data-testid*="UserAvatar"]) div[data-testid="stChatMessageContent"] p,
  div[data-testid="stChatMessage"]:has([data-testid*="UserAvatar"]) div[data-testid="stChatMessageContent"] {
    color: #ffffff !important;
  }

  /* ASSISTANT message: left aligned, dark glass */
  div[data-testid="stChatMessage"]:has([data-testid*="AssistantAvatar"]) {
    justify-content: flex-start !important;
  }
  div[data-testid="stChatMessage"]:has([data-testid*="AssistantAvatar"]) div[data-testid="stChatMessageContent"] {
    background: linear-gradient(
      145deg,
      rgba(18, 12, 42, 0.80) 0%,
      rgba(10, 6, 22, 0.65) 100%
    ) !important;
    border: 1px solid rgba(216, 216, 232, 0.10) !important;
  }

  /* --- Clean circular avatars for the SVG data URLs injected from Python --- */
  div[data-testid="stChatMessage"] [data-testid*="Avatar"] {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    width: 36px !important;
    height: 36px !important;
    min-width: 36px !important;
    min-height: 36px !important;
    border-radius: 50% !important;
    overflow: hidden !important;
    margin-top: 2px !important;
    padding: 0 !important;
    flex-shrink: 0 !important;
  }

  div[data-testid="stChatMessage"] [data-testid*="Avatar"] img {
    width: 100% !important;
    height: 100% !important;
    border-radius: 50% !important;
    object-fit: cover !important;
    display: block !important;
  }

  /* Soft glow behind the assistant's orb avatar */
  div[data-testid="stChatMessage"] [data-testid*="AssistantAvatar"] {
    box-shadow:
      0 0 0 1px rgba(167, 139, 250, 0.25),
      0 4px 14px rgba(139, 92, 246, 0.32) !important;
  }

  div[data-testid="stChatMessage"] [data-testid*="UserAvatar"] {
    box-shadow:
      0 0 0 1px rgba(255, 255, 255, 0.18),
      0 4px 10px rgba(0, 0, 0, 0.28) !important;
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

  [data-testid="stMain"],
  section.main,
  .main {
    min-height: 0 !important;
    height: auto !important;
    justify-content: flex-start !important;
    display: flex !important;
    flex-direction: column !important;
  }

  [data-testid="stMain"] > div,
  [data-testid="stMainBlockContainer"],
  div.block-container {
    flex: 0 0 auto !important;
    min-height: 0 !important;
  }

  [data-testid="stBottom"],
  [data-testid="stBottomBlockContainer"] {
    position: relative !important;
    left: auto !important;
    right: auto !important;
    bottom: auto !important;
    top: auto !important;
    transform: none !important;
    width: 100% !important;
    max-width: 100% !important;
    padding: 0 !important;
    margin: 0 !important;
    flex: 0 0 auto !important;
    min-height: 0 !important;
  }

  div[data-testid="stChatInput"] {
    position: relative !important;
    left: auto !important;
    right: auto !important;
    top: auto !important;
    bottom: auto !important;
    transform: none !important;
    z-index: 1;
    width: 100% !important;
    max-width: 760px !important;
    margin: 0.75rem auto 0 auto !important;
    padding: 0.6rem !important;
    border-radius: 16px;
    border: 1px solid rgba(228, 228, 234, 0.14);
    background: rgba(10, 10, 16, 0.22) !important;
    backdrop-filter: blur(12px) !important;
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.40);
  }

  div[data-testid="stChatInput"] textarea {
    min-height: 3.6rem !important;
  }

  /*
   * Desktop: keep fixed chat input clear of the left sidebar.
   * Main content already flows correctly; fixed bars need explicit offset.
   */
  @media (min-width: 769px) {
    div.block-container {
      padding-left: 1.8rem !important;
      padding-right: 1.8rem !important;
      margin-left: auto !important;
      margin-right: auto !important;
    }

    div[data-testid="stChatInput"] {
      max-width: 760px !important;
      margin-left: auto !important;
      margin-right: auto !important;
    }
  }

  div[data-testid="stChatInput"] textarea,
  div[data-testid="stChatInput"] textarea:focus,
  div[data-testid="stChatInput"] textarea:hover,
  div[data-testid="stChatInput"] textarea:active {
    background: transparent !important;
    background-color: transparent !important;
    border: 1px solid rgba(228, 228, 234, 0.10) !important;
    color: var(--orion-text) !important;
    border-radius: 10px !important;
    min-height: 2.9rem !important;
    padding: 0.95rem 1.05rem !important;
    box-shadow: none !important;
    outline: none !important;
  }

  /* Light mode support for chat input visibility */
  @media (prefers-color-scheme: light) {
    div[data-testid="stChatInput"] textarea,
    div[data-testid="stChatInput"] textarea:focus,
    div[data-testid="stChatInput"] textarea:hover,
    div[data-testid="stChatInput"] textarea:active {
      color: #1a1a1a !important;
      background: rgba(255, 255, 255, 0.95) !important;
      border: 1px solid rgba(0, 0, 0, 0.15) !important;
    }
    
    div[data-testid="stChatInput"] {
      background: rgba(255, 255, 255, 0.85) !important;
      border: 1px solid rgba(0, 0, 0, 0.12) !important;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1) !important;
    }
  }

  div[data-testid="stChatInput"] textarea:-webkit-autofill,
  div[data-testid="stChatInput"] textarea:-webkit-autofill:hover,
  div[data-testid="stChatInput"] textarea:-webkit-autofill:focus {
    -webkit-text-fill-color: var(--orion-text) !important;
    -webkit-box-shadow: 0 0 0 1000px transparent inset !important;
    transition: background-color 9999s ease-in-out 0s !important;
  }

  div[data-testid="stChatInput"] textarea::placeholder {
    color: #000000 !important;
  }


  @media (max-width: 768px) {
    div[data-testid="stChatInput"] {
      max-width: 100% !important;
    }
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
  [data-testid="stMain"],
  [data-testid="stMainBlockContainer"],
  [data-testid="stBottomBlockContainer"],
  [data-testid="stBottom"],
  [data-testid="stToolbar"],
  [data-testid="stStatusWidget"],
  [data-testid="stFooter"],
  [data-testid="stDecoration"],
  [data-testid="stHeader"],
  section,
  main {
    background: transparent !important;
    background-color: transparent !important;
  }

  [data-testid="stBottom"] > div,
  [data-testid="stBottomBlockContainer"] > div {
    background: transparent !important;
    background-color: transparent !important;
  }

  div[data-testid="stChatMessage"],
  div[data-testid="stChatMessageContainer"],
  div[data-testid="stChat"] {
    background: transparent !important;
  }
</style>
"""
