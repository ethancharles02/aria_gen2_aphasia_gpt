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
STREAM_BATCH_PERIOD_MS = 200
STREAM_OVER_WIFI = True
# Connects to the glasses over wifi. Must have DEVICE_IP set in agpt_secrets for this to work
INITIAL_CONNECTION_OVER_WIFI = True

# --- Debug ---
# Disables audio transcription and instead shows the temperature
DISPLAY_TEMPERATURE = True

# --- Audio Transcription ---
# See https://github.com/openai/whisper/blob/main/model-card.md
WHISPER_MODEL_NAME = "base.en"
AUDIO_SAMPLE_RATE = 16000
# How long to transcribe before forcing a phrase end
PHRASE_TIMEOUT_SEC = 30.0
TRANSCRIPTION_WARMUP_SEC = 3.0
# Confidence of no speech within threshold time (ie. this percent of samples didn't have speech detected)
SR_THRESHOLD = 0.95
# Threshold of time in seconds
SR_THRESHOLD_TIME = 2
# Can be 10, 20, or 30 milliseconds
FRAME_DURATION_MS = 30
# Time to look back to decide if speaking has started
START_TRANSCRIPTION_WINDOW_S = 1.0
# Threshold of frames that were detected as speech in the window
START_TRANSCRIPTION_THRESHOLD = 0.7

# --- EyeGaze ---
# B, G, R
EYEGAZE_COLOR = (255, 0, 255)
EYEGAZE_RADIUS = 5
# Time in milliseconds to allow the eyegaze to be placed on the image (ie. if the image was taken at
# 100ms but the eyegaze was at 300ms and the threshold was 100ms, it wouldn't be added to that
# image)
EYEGAZE_THRESHOLD_TIME = 500