# Aria Gen2 Aphasia GPT

A real-time AI assistant system that processes video and audio streams from Project Aria Gen2 smart glasses using vision and speech models, combined with a General User Model (GUM) framework for understanding and tracking user behavior.

## Overview

This project integrates Project Aria Gen2 smart glasses with AI models to create a context-aware assistant system. It captures what users see and hear in real-time, processes this information through vision and speech language models, and maintains a model of user behavior and observations.

**Key Features:**
- **Real-time Video Processing**: Captures and analyzes video streams from Aria Gen2 glasses using vision LLMs
- **Live Audio Transcription**: Processes audio streams with OpenAI's Whisper for real-time speech-to-text
- **General User Model (GUM)**: Tracks observations, generates propositions, and builds a knowledge base about user behavior and context
- **Context-Aware Responses**: Uses transcription context, image analysis, and user history to generate informed responses

## Installation & Setup

### Prerequisites
- Python 3.10-3.12
- Project Aria Gen2 smart glasses
- Linux environment (also tested on WSL)

### Initial Setup

1. **Create secrets file** (`agpt_lib/agpt_secrets.py`):
   ```python
   STREAMING_IP = "https://your_server_ip:6768"     # HTTPS URL with port for streaming
   USER_NAME = "your_name"                          # User identifier for the GUM system
   VISION_LLM_IDENTIFIER = "llm_identifier"         # Vision model identifier
   VISION_LLM_API_BASE = "http://localhost:1234/v1" # Vision LLM API endpoint
   VISION_LLM_API_TOKEN = "your_api_token"          # Vision LLM API token
   TEXT_LLM_IDENTIFIER = "llm_identifier"           # Text model identifier
   TEXT_LLM_API_BASE = "http://localhost:1234/v1"   # Text LLM API endpoint
   TEXT_LLM_API_TOKEN = "your_api_token"            # Text LLM API token
   DEVICE_IP = "your_glasses_ip"                    # Aria glasses IP address, if connected over USB,
                                                    # the program will tell you the IP on connection
   ```

2. **Set up the virtual environment**:
    On Linux:
    ```bash
    bash misc_scripts/setup_venv.sh
    ```
    This script will create a `.venv` directory and install all required dependencies.

    On WSL:
    ```bash
    bash misc_scripts/setup_wsl_aria_env.sh
    ```
    Installs all necessary packages for the WSL environment
3. **Activate the environment**:
   ```bash
   source .venv/bin/activate
   ```

### Configuration

Edit `agpt_lib/agpt_secrets.py` to configure your LLM endpoints and credentials.

Edit `agpt_lib/agpt_config.py` to customize:
- **Streaming**: Device connection, batch period, IP settings
- **Audio Transcription**: Whisper model size, confidence thresholds
- **Certification**: Paths to Aria streaming certificates

**LLM Setup:**
The system supports any OpenAI-compatible LLM API. Set your API endpoints and authentication tokens in `agpt_secrets.py`:
- Vision LLM configuration
- Text LLM configuration

Both can point to the same or different LLM instances.

## Usage

### Running the Main Application

```bash
python main.py
```

This will:
1. Connect to Aria Gen2 glasses
2. Start streaming video and audio
3. Initialize the GUM system with observers
4. Begin real-time processing of visual and audio data
5. Run indefinitely until interrupted (Ctrl+C)

### Key Components

#### Image Observer
Processes video frames from Aria glasses:
- Transcribes visible text and content
- Generates detailed descriptions of user environment
- Maintains a history of recent frames for context
- Uses configurable vision LLM for analysis

#### Audio Transcription Worker
Real-time speech transcription:
- Streams audio through Whisper ASR model
- Detects speech activity and segments phrases
- Configurable confidence thresholds and timeouts
- Thread-based background processing

#### General User Model (GUM)
Central framework managing observations and propositions:
- **Observations**: Raw data captured by observers (images, transcriptions)
- **Propositions**: Generated hypotheses about user behavior
- **Database**: SQLite backend for persistence

## Development

### Streaming Configuration
Streaming settings can be defined in JSON format:
- `agpt_streaming.json`: Custom image stream configuration
- `streaming.json`: Fallback configuration

## Certificates & Authentication

Aria glasses require SSL certificates for secure streaming:
- **Subscriber Certificate**: `~/.aria/streaming-certs/persistent/subscriber.pem`
- **Subscriber Key**: `~/.aria/streaming-certs/persistent/subscriber-key.pem`

See [Project Aria documentation](https://facebookresearch.github.io/projectaria_tools/gen2/ark/client-sdk/authentication) for setup.

## References

- [Project Aria Tools Documentation](https://facebookresearch.github.io/projectaria_tools/gen2/)
- [Whisper Speech Recognition](https://github.com/openai/whisper)
- [OpenAI API Documentation](https://platform.openai.com/docs)