# Project Architecture

The repository contains a lightweight GUI for interacting with an Ollama‑based LLM and executing shell commands.

## Top‑level layout
- `app.py` – Main application entry point. Implements the Qt UI, two worker threads (`OllamaWorker`, `CommandWorker`) and logic to stream responses or command output.
- `requirements.txt` – Python dependencies used by the app (PySide6, requests).
- `README.md` – Usage instructions and high‑level design notes.
- `.venv/` – A virtual environment holding installed packages. It is automatically created when you run `pip install -r requirements.txt`.

No additional source directories or tests are currently present; all logic resides in `app.py` for quick prototyping.
