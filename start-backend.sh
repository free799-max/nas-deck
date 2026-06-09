#!/bin/bash
export PYTHONPATH=/home/free/code/nas-deck/backend
exec /home/free/code/nas-deck/backend/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 5001
