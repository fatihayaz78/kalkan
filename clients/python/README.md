# kalkan-client

```bash
pip install "git+https://github.com/fatihayaz78/kalkan.git#subdirectory=clients/python"
```

```python
from kalkan_client import KalkanClient, InjectionBlocked

kalkan = KalkanClient("http://localhost:8088", api_key="...", fail_mode="closed")

try:
    kalkan.guard(user_message)
except InjectionBlocked as e:
    reply = "Bu isteği işleyemiyorum."   # do not call the LLM
```
See `docs/INTEGRATION.md` for RAG, chat transcripts, async and other languages.
