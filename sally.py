# sally.py
import uvicorn

# 👇 force-load modules that register routes / websockets
import routes  # noqa: F401
import websocket  # noqa: F401
from app_instance import PORT, app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
