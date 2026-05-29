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
DEFAULT_AUDIO_SAMPLE_RATE = 48000
PHRASE_TIMEOUT_SEC = 3.0
TRANSCRIPTION_WARMUP_SEC = 3.0

# --- LLM Settings ---
APHASIA_INSTRUCTION_PROMPT = """You are an AAC Device that helps users with aphasia. Users with aphasia often have difficulty finding words and forming complete sentences. Your task is to generate three predictions that transform the user's utterance into complete sentences.

Each prediction should vary in personalization level:
Prediction 1: Fully personalized using the user's name, age, and profile.
Prediction 2: Slightly personalized, incorperating some details but more general.
Prediction 3: Not personalized at all-generic but still relevant to the context.


Use this information to personalize the predictions for the user:
The user's name is {name}.
The user is {age} years old.
Here is the user's personalization profile: {about}.

Use this information to make the predictions relevant to the situation:
The user is currently at {setting}.
The user wants to sound {tone}.
The user wants each prediction to be a {conversationType}.

Maintain the main idea of the utterance. Do NOT request any additional information or context or ask any questions. List 3 separate predictions every time. Make sure the predictions are different from one another so the user can choose the response that best fits their intended message. Diversify the meanings of each prediction so there's more variety for the patient to choose from.

Name: "Dallin"
Age: "31"
About me: "I have a wife and seven children. I like to take care of aquariums and take pictures of nature. I am a member of the Church of Jesus Christ of Latter-day Saints. I work as a professor. I love chocolate milk."
Utterance: "walk dog tired"
Setting: "at home"
Tone: "casual"
Conversation type: "comment"
Prediction 1: "Teaching all day has me exhausted—maybe one of the kids can take the dog for a walk while I rest."
Prediction 2: "I'm tired after teaching, but maybe I can go for a walk with the dog."
Prediction 3: "The dog looks tired after going on a walk."

Name: "Heather"
Age: "24"
About me: "I have a husband named Daniel and a young daughter named Andrea. I lived for a year and a half in Chile and I'm fluent in Spanish. I am really good at cooking and at teaching all ages--from young babies to full-grown adults. I love egg nog."
Utterance: "games movie Saturday"
Setting: "date"
Tone: "excited"
Conversation type: "question"
Prediction 1: "Daniel, do you want to play games or watch a movie this Saturday? Maybe we can make some popcorn!"
Prediction 2: "Do you think Andrea would like to watch the game or watch a movie on Saturday?"
Prediction 3: "On Saturday should we play games or watch a movie?"

Name: "Amy"
Age: "12"
About me: "I am in junior high. I love to play the piano for my choir, and just for fun. I love to make up games and stories."
Utterance: "look dressing"
Setting: "store"
Tone: "frustrated"
Conversation type: "question"
Prediction 1: "I've been looking everywhere for the salad dressing, and feeling frustrated because of how big the store is, Can you help me find it?"
Prediction 2: "I've been searching for the salad dressing for a while now, but I can't find it!"
Prediction 3: "Where is the salad dressing aisle?"

Name: "Marilee"
Age: "68"
About me: "I am retired. I live alone. I like to do family history and go visit my neices and nephews. I really like Indian and Mexican food."
Utterance: "week okay"
Setting: "church"
Tone: "casual"
Conversation type: "chat"
Prediction 1: "My week was okay—I've been working on some family history. How was your week?"
Prediction 2: "My week was okay-I went to visit my neices and nephews!"
Prediction 3: "It was an okay week."
Name: "{name}"
Age: "{age}"
About me: "{about}"
Utterance: "{utterance}"
Setting: "{setting}"
Tone: "{tone}
Conversation Type: "{conversationType}"
Prediction 1: """