from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_openai import ChatOpenAI


def get_openai_llm(model: str = "gpt-4o-mini", temperature: float = 0) -> ChatOpenAI:
    llm = ChatOpenAI(model=model, temperature=temperature)
    return llm


def get_ollama_llm(model: str = "qwen3.5:9b", temperature: float = 0) -> ChatOllama:
    llm = ChatOllama(model=model, temperature=temperature)
    return llm


def get_ollama_embedding_model(model: str = "qwen3-embedding:0.6b") -> OllamaEmbeddings:
    embeddings = OllamaEmbeddings(model=model)
    return embeddings


if __name__ == "__main__":
    print(get_ollama_llm().invoke("Hello, how are you?"))
