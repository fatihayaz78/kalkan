"""Example: filter retrieved RAG chunks before they enter the prompt (indirect injection)."""
from kalkan_client import KalkanClient

kalkan = KalkanClient("http://localhost:8088", api_key=None)


def safe_context(chunks: list[str]) -> list[str]:
    results = kalkan.check_documents(chunks)
    return [c for c, r in zip(chunks, results) if r.decision == "allow"]
