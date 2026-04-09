"""
TiniX Story 1.0 - Entry Point
Khởi động cả Gradio UI và FastAPI server
"""
import os
import sys
import threading
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("run")


def start_gradio():
    """Khởi động Gradio UI trên port 7860"""
    try:
        from app import main
        main()
    except Exception as e:
        logger.error(f"Gradio startup failed: {e}")
        sys.exit(1)


def start_fastapi():
    """Khởi động FastAPI server trên port 8000"""
    try:
        import uvicorn
        from main_api import app
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    except Exception as e:
        logger.error(f"FastAPI startup failed: {e}")
        sys.exit(1)


def main():
    mode = os.getenv("TINIX_MODE", "all").lower()

    if mode == "api":
        logger.info("Starting TiniX Story in API-only mode (port 8000)")
        start_fastapi()
    elif mode == "ui":
        logger.info("Starting TiniX Story in Gradio UI mode (port 7860)")
        start_gradio()
    else:
        logger.info("Starting TiniX Story - All services")
        logger.info("  → FastAPI: http://localhost:8000")
        logger.info("  → Gradio UI: http://localhost:7860")

        # FastAPI in background thread
        api_thread = threading.Thread(target=start_fastapi, daemon=True)
        api_thread.start()

        # Gradio in main thread (blocks)
        start_gradio()


if __name__ == "__main__":
    main()
