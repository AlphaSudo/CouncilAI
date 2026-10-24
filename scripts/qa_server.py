from pathlib import Path
import tempfile
from zerowall.api import create_app
from zerowall.settings import Settings
import uvicorn

s = Settings(Path(tempfile.mkdtemp(prefix="zerowall-browser-qa-")))
s.api_key = ""
s.openrouter_api_key = ""
s.openrouter_enabled = False
s.direct_keys = {}
s.direct_free_confirmed = False
s.tavily_api_key = ""
uvicorn.run(create_app(s), host="127.0.0.1", port=8001, log_level="warning")
