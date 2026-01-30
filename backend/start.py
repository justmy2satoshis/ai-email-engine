"""Launcher script for init-manager compatibility.
Starts uvicorn programmatically instead of via CLI.
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8410,
        reload=False,
        log_level="info",
    )
