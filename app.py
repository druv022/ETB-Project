import os
from typing import List, Dict

import requests
import streamlit as st
from dotenv import load_dotenv


load_dotenv()


SYSTEM_PROMPT = '''You are Orion, an intelligent conversational assistant for IndMex. 
Your role is to help C-suite executives (CEO, CFO, COO) retrieve accurate 
information from IndMex's internal data — including sales, revenue, and 
financial data stored across multiple formats and systems.

---

YOUR ONLY JOB IN THIS CONVERSATION:
Understand what the executive is asking and make sure the request is 
specific enough to retrieve the right data. You do NOT retrieve data 
yourself. Once the request is clear, you confirm it and hand it off.

---

HOW TO BEHAVE:

1. When the user sends a question, evaluate whether it is specific enough 
   to retrieve data. A good question has at least:
   - A clear TOPIC (e.g. revenue, profit margin, sales by region)
   - A TIME PERIOD (e.g. Q3 2024, last month, full year 2023)
   - A SCOPE if needed (e.g. which product line, which region, which team)

2. If the question is missing one or more of these elements, ask ONE 
   clarifying question. Ask only the most important missing piece. 
   Do not ask multiple questions at once.

3. If the question is already specific enough, respond with:
   - A brief confirmation of what you understood
   - A structured summary of the request labeled as: 
     "READY TO RETRIEVE:" followed by the refined query in one sentence.

4. Keep your tone professional, concise, and executive-appropriate. 
   No unnecessary explanations.

---

EXAMPLES OF AMBIGUOUS QUESTIONS (require follow-up):
- "How are we doing?" → Missing: topic, time period, scope
- "Show me the sales numbers" → Missing: time period, which product/region
- "What's our financial situation?" → Missing: specific metric, time period

EXAMPLES OF CLEAR QUESTIONS (ready to retrieve):
- "What was IndMex's total revenue in Q3 2024 broken down by product line?"
- "Compare net profit margin for 2023 vs 2024 across all business units."
- "What were the top 5 customers by revenue in the last fiscal year?"

---

IMPORTANT RULES:
- Never make up data or answer with numbers you don't have.
- Never ask more than one clarifying question per turn.
- Never repeat the same clarifying question twice.
- If after 2 rounds of clarification the question is still vague, 
  make a reasonable assumption, state it clearly, and proceed to 
  "READY TO RETRIEVE."'''


def ensure_session_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages: List[Dict[str, str]] = []


def call_indmex_agent(messages: List[Dict[str, str]]) -> str:
    """
    Call a local Ollama-compatible endpoint exposed at
    https://genai.rcac.purdue.edu/api using the llama4:latest model.
    No authentication or API key is required.
    """
    url = "https://genai.rcac.purdue.edu/api/chat/completions"

    token = os.getenv("PURDUE_API_KEY")
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = {
        "model": "llama4:latest",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            *messages,
        ],
        "temperature": 0.2,
    }

    response = requests.post(url, json=payload, headers=headers, timeout=60)

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        if response.status_code == 401:
            return (
                "Orion could not access the local model API (401 Unauthorized).\n\n"
                "The endpoint at https://genai.rcac.purdue.edu/api/chat/completions requires "
                "a valid PURDUE_API_KEY. Please make sure it is set in your .env file or "
                "environment as PURDUE_API_KEY."
            )
        return (
            f"Orion received an HTTP error from the local model API "
            f"({response.status_code}): {exc}"
        )

    data = response.json()

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return "Orion could not parse a valid response from the local model API."


def main():
    st.set_page_config(
        page_title="Orion",
        page_icon="🛰️",
        layout="centered",
    )

    st.markdown(
        """
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

          /* Center and frosted-glass style for the chat input */
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

          /* Keep send button legible */
          div[data-testid="stChatInput"] button {
            color: var(--orion-text) !important;
          }

          /* Style quick action buttons */
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

          /* White text inside expander/content */
          .stMarkdown, .stText, .stCaption {
            color: var(--orion-text) !important;
          }

          .stCaption {
            color: var(--orion-muted) !important;
          }

          /* Ensure the chat area doesn't cover the background */
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
        """,
        unsafe_allow_html=True,
    )

    ensure_session_state()

    st.title("Orion")
    st.caption(
        "Executive-focused assistant that refines your data requests so they are ready for retrieval from IndMex's internal systems."
    )

    with st.expander("What Orion does", expanded=False):
        st.markdown(
            """
            - **Clarifies requests** from C‑suite leaders so they can be executed by downstream data systems.  
            - **Does not retrieve or fabricate data**; it only structures the request.  
            - Ensures each request has a **topic**, **time period**, and **scope** where needed.  
            - Produces a final line starting with **`READY TO RETRIEVE:`** when the request is clear.
            """
        )

    # Render chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Input at the bottom
    user_input = st.chat_input("Describe the information you need from IndMex's data...")

    if user_input:
        # Add user message to history and display it
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Orion is reviewing your request..."):
                reply = call_indmex_agent(st.session_state.messages)
                st.markdown(reply)
                st.session_state.messages.append(
                    {"role": "assistant", "content": reply}
                )


if __name__ == "__main__":
    main()

