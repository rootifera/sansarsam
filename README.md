# Sansarsam

Sansarsam is a lightweight PySide6 desktop UI wrapper for the Greaseweazle CLI (`gw`).

## Requirements

- Python 3.10+
- `gw` available on PATH **or** selected via the UI executable picker
- Dependencies from `requirements.txt`

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

## Notes

- The app does **not** implement hardware logic; it only invokes `gw` commands.
- Both workflows (write/create) stream live CLI output into the UI log area.
