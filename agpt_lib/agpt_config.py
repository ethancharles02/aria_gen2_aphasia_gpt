# WARNING: For first time setup, you will need to create an agpt_secrets.py file in this directory
# that sets the following variables:
# STREAMING_IP = your desired Wi-Fi IP server that is running main.py
# LLM_API_BASE = OpenAI format ip to connect to
# LLM_API_TOKEN = LLM api token if applicable
# DEVICE_IP = IP of the glasses (if connecting over Wi-Fi. see INITIAL_CONNECTION_OVER_WIFI), can be an empty string otherwise

# --- Certification ---
# Keys produced by Aria glasses in this path below (see
# https://facebookresearch.github.io/projectaria_tools/gen2/ark/client-sdk/authentication)
CERT_PATH = "~/.aria/streaming-certs/persistent/subscriber.pem"
KEY_PATH = "~/.aria/streaming-certs/persistent/subscriber-key.pem"

# --- Streaming ---
# Should be device config name if streaming from device, otherwise it should be a json file. Decides
# based on if the string ends in .json
STREAM_CONFIG_NAME = "agpt_lib/agpt_streaming.json"
# STREAM_CONFIG_NAME = "agpt_lib/streaming.json"
# STREAM_CONFIG_NAME = "streaming"
# Amount of time to batch messages to send over the network. For Wi-Fi streaming, this should be
# around 200 to prevent overheating (see
# https://facebookresearch.github.io/projectaria_tools/gen2/ark/client-sdk/streaming#message-batching)
STREAM_OVER_WIFI = True
STREAM_BATCH_PERIOD_MS = 200
# Connects to the glasses over wifi. Must have DEVICE_IP set in agpt_secrets for this to work
INITIAL_CONNECTION_OVER_WIFI = False

# --- Debug ---
# Disables audio transcription and instead shows the temperature
DISPLAY_TEMPERATURE = True

# --- Audio Transcription ---
# See https://github.com/openai/whisper/blob/main/model-card.md
WHISPER_MODEL_NAME = "base.en"
WHISPER_SAMPLE_RATE = 16000
AUDIO_SAMPLE_RATE = 16000
PHRASE_TIMEOUT_SEC = 3.0
TRANSCRIPTION_WARMUP_SEC = 3.0