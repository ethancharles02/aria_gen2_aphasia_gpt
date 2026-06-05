#!/usr/bin/env bash
# Virtual environment setup script for Aria Gen2 Aphasia GPT
# This script creates a Python virtual environment and installs all required dependencies
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$REPO_ROOT/.venv"
PYTHON_BIN="$VENV_DIR/bin/python"

log() {
    echo "[venv-setup] $*"
}

setup_python_env() {
    if [[ ! -d "$VENV_DIR" ]]; then
        log "Creating virtual environment at $VENV_DIR"
        python3.12 -m venv "$VENV_DIR"
    else
        log "Using existing virtual environment at $VENV_DIR"
    fi

    source "$VENV_DIR/bin/activate"

    log "Installing Python dependencies"
    python -m pip install --upgrade pip
    python -m pip install \
        projectaria-client-sdk \
        rerun-sdk \
        torch \
        openai-whisper \
        transformers \
        openai \
        SQLAlchemy \
        sqlalchemy-utils \
        pydantic \
        scikit-learn \
        numpy \
        aiosqlite \
        greenlet \
        persist-queue \
        python-dotenv \
        pydub \
        opencv-python \
        webrtcvad-wheels

    deactivate
}

validate_install() {
    log "Validating Aria imports"
    "$PYTHON_BIN" -c "import aria.sdk_gen2; import aria.stream_receiver; print('Aria SDK import OK')"
}

main() {
    setup_python_env
    validate_install
}

main "$@"
