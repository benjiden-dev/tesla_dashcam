"""Run the web UI: python -m webui"""

import uvicorn

from . import config

if __name__ == "__main__":
    uvicorn.run(
        "webui.app:app",
        host="0.0.0.0",
        port=config.PORT,
        log_level="info",
    )
