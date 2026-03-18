## Orion – Local Llama Chatbot

This Streamlit app runs **Orion**, a clarifying assistant for IndMex executives, backed by a
local **Ollama-compatible** API instead of OpenAI.

- **Model**: `llama4:latest`  
- **Base URL**: `https://genai.rcac.purdue.edu/api/chat/completions`  
- **Authentication**: **No API key required** (no `.env` configuration is needed)

### Setup

```bash
python -m venv .venv
.venv\Scripts\activate    # On Windows
pip install -r requirements.txt
```

### Run the app

```bash
streamlit run app.py
```

### Environment variables / .env

This version of the app **does not use any API key** and **does not read a `.env` file**.  
You can ignore any previous instructions referring to `OPENAI_API_KEY`; they are no longer needed.

