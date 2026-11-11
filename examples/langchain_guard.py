"""Example: Kalkan as the first step of a LangChain (LCEL) chain.

    chain = kalkan_guard | prompt | llm
"""
from langchain_core.runnables import RunnableLambda

from kalkan_client import KalkanClient

kalkan = KalkanClient("http://localhost:8088", api_key=None)


def _guard(inputs: dict) -> dict:
    kalkan.guard(inputs["question"])  # raises InjectionBlocked
    return inputs


kalkan_guard = RunnableLambda(_guard)
