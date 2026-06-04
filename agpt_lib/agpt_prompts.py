# ----- IMAGE PROMPTS -----
TRANSCRIPTION_PROMPT = """You will be given images from the perspective of the user wearing smart glasses. There is a fish eye distortion as a result. There may be a magenta square included which indicates where the user is looking

Transcribe in markdown ALL the content from the provided images, paying special attention to text. Also describe the environment in detail.

NEVER SUMMARIZE ANYTHING. You must transcribe everything EXACTLY, word for word, but don't repeat yourself.

If there is not any legible text to transcribe, you may say so

Create a FINAL structured markdown transcription."""

SUMMARY_PROMPT = """You will be given images from the perspective of the user wearing smart glasses. There is a fish eye distortion as a result. There may be a magenta square included which indicates where the user is looking

Provide a detailed description of the actions occuring across the provided images. The images are in the order they were taken.

Include as much relevant detail as possible, but remain concise.

Generate a handful of bullet points and reference *specific* actions the user is taking.

Keep in mind that the images show what the user is viewing. It may not be what the user is actively doing or what they believe, so practice caution when making assumptions."""

# ----- TEXT PROMPTS -----
AUDIT_PROMPT = """You are a data privacy compliance assistant for a large language model (LLM).

Here are some past interactions {user_name} had with an LLM

## Past Interactions

{past_interaction}

## Task

{user_name} currently is looking at the following:

User Input
---
{user_input}
---

Given {user_name}'s input, analyze and respond in structured JSON format with the following fields:

1. `is_new_information`: Boolean — Does the user's message contain new information compared to the past interactions?
2. `data_type`: String — What type of data is being disclosed (e.g., "Banking credentials and financial account information", "Sensitive topics", "None")?
3. `subject`: String — Who is the primary subject of the disclosed data?
4. `recipient`: String — Who or what is the recipient of the information (e.g., "An AI model that provides conversational assistance")?
5. `transmit_data`: Boolean — Based on how the user handles privacy in their past interactions, should this data be transmitted to the model?

Example output format:
{
  "is_new_information": true,
  "data_type": "[fill in]",
  "subject": "{user_name}",
  "recipient": "An AI model that generates inferences about the user to help in downstream tasks.",
  "transmit_data": true
}"""


PROPOSE_PROMPT = """You are a helpful assistant tasked with analyzing user behavior based on transcribed activity.

# Analysis

Using image and audio transcriptions of {user_name}'s activity, analyze {user_name}'s current activities, behavior, and preferences. Draw insightful, concrete conclusions.

To support effective information retrieval (e.g., using BM25), your analysis must **explicitly identify and refer to specific named entities** mentioned in the transcript. This includes applications, websites, documents, people, organizations, tools, and any other proper nouns. Avoid general summaries—**use exact names** wherever possible, even if only briefly referenced.

Consider these points in your analysis:

- What specific tasks or goals is {user_name} actively working towards, as evidenced by named files, apps, platforms, or individuals?
- What applications, documents, or content does {user_name} clearly prefer engaging with? Identify them by name.
- What does {user_name} choose to ignore or deprioritize, and what might this imply about their focus or intentions?
- What are the strengths or weaknesses in {user_name}'s behavior or tools? Cite relevant named entities or resources.

Provide detailed, concrete explanations for each inference. **Support every claim with specific references to named entities in the transcript.**

## Evaluation Criteria

For each proposition you generate, evaluate its strength using two scales:

### 1. Confidence Scale

Rate your confidence based on how clearly the evidence supports your claim. Consider:

- **Direct Evidence**: Is there direct interaction with a specific, named entity (e.g., opened “Notion,” responded to “Slack” from “Alex”)?
- **Relevance**: Is the evidence clearly tied to the proposition?
- **Engagement Level**: Was the interaction meaningful or sustained?

Score: **1 (weak support)** to **10 (explicit, strong support)**. High scores require specific named references.

### 2. Decay Scale

Rate how long the proposition is likely to stay relevant. Consider:

- **Urgency**: Does the task or interest have clear time pressure?
- **Durability**: Will this matter 24 hours later or more?

Score: **1 (short-lived)** to **10 (long-lasting insight or pattern)**.

# Input

Below is a set of transcribed actions and interactions that {user_name} has performed:

## User Activity Transcriptions

{inputs}

# Task

Generate **at least 5 distinct, well-supported propositions** about {user_name}, each grounded in the transcript.

Be conservative in your confidence estimates. Just because an application appears on {user_name}'s screen does not mean they have deeply engaged with it. They may have only glanced at it for a second, making it difficult to draw strong conclusions.

Assign high confidence scores (e.g., 8-10) only when the transcriptions provide explicit, direct evidence that {user_name} is actively engaging with the content in a meaningful way. Keep in mind that the content on the screen is what the user is viewing. It may not be what the user is actively doing, so practice caution when assigning confidence.

Generate propositions across the scale to get a wide range of inferences about {user_name}.

Return your results in this exact JSON format:

{
  "propositions": [
    {
      "proposition": "[Insert your proposition here]",
      "reasoning": "[Provide detailed evidence from specific parts of the transcriptions to clearly justify this proposition. Refer explicitly to named entities where applicable.]",
      "confidence": "[Confidence score (1-10)]",
      "decay": "[Decay score (1-10)]"
    },
    ...
  ]
}"""

SIMILAR_PROMPT = """You will label sets of propositions based on how similar they are to each other.

# Propositions

{body}

# Task

Use exactly these labels:

(A) IDENTICAL - The propositions say practically the same thing.
(B) SIMILAR   - The propositions relate to a similar idea or topic.
(C) UNRELATED - The propositions are fundamentally different.

Always refer to propositions by their numeric IDs.

Return **only** JSON in the following format:

{
  "relations": [
    {
      "source": <ID>,
      "label": "IDENTICAL" | "SIMILAR" | "UNRELATED",
      "target": [<ID>, ...] // empty list if UNRELATED
    }
    // one object per judgement, go through ALL propositions in the input.
  ]
}"""

REVISE_PROMPT = """You are an expert analyst. A cluster of similar propositions are shown below, followed by their supporting observations.

Your job is to produce a **final set** of propositions that is clear, non-redundant, and captures everything about the user, {user_name}.

To support information retrieval (e.g., with BM25), you must **explicitly identify and preserve all named entities** from the input wherever possible. These may include applications, websites, documents, people, organizations, tools, or any other specific proper nouns mentioned in the original propositions or their evidence.

You MAY:

- **Edit** a proposition for clarity, precision, or brevity.
- **Merge** propositions that convey the same meaning.
- **Split** a proposition that contains multiple distinct claims.
- **Add** a new proposition if a distinct idea is implied by the evidence but not yet stated.
- **Remove** propositions that become redundant after merging or splitting.

You should **liberally add new propositions** when useful to express distinct ideas that are otherwise implicit or entangled in broader statements—but never preserve duplicates.

When editing, **retain or introduce references to specific named entities** from the evidence wherever possible, as this improves clarity and retrieval fidelity.

Edge cases to handle:

- **Contradictions** - If two propositions conflict, keep the one with stronger supporting evidence, or merge them into a conditional statement. Lower the confidence score of weaker or uncertain claims.
- **No supporting observations** - Keep the proposition, but retain its original confidence and decay unless justified by new evidence.
- **Granularity mismatch** - If one proposition subsumes others, prefer the version that avoids redundancy while preserving all distinct ideas.
- **Confidence and decay recalibration** - After editing, merging, or splitting, update the confidence and decay scores based on the final form of the proposition and evidence.

General guidelines:

- Keep each proposition clear and concise (typically 1-2 sentences).
- Maintain all meaningful content from the originals.
- Provide a brief reasoning/evidence statement for each final proposition.
- Confidence and decay scores range from 1-10 (higher = stronger or longer-lasting).

## Evaluation Criteria

For each proposition you revise, evaluate its strength using two scales:

### 1. Confidence Scale

Rate your confidence in the proposition based on how directly and clearly it is supported by the evidence. Consider:

- **Direct Evidence**: Is the claim directly supported by clear, named interactions in the observations?
- **Relevance**: Is the evidence closely tied to the proposition?
- **Completeness**: Are key details present and unambiguous?
- **Engagement Level**: Does the user interact meaningfully with the named content?

Score: **1 (weak/assumed)** to **10 (explicitly demonstrated)**. High scores require direct and strong evidence from the observations.

### 2. Decay Scale

Rate how long the insight is likely to remain relevant. Consider:

- **Immediacy**: Is the activity time-sensitive?
- **Durability**: Will the proposition remain true over time?

Score: **1 (short-lived)** to **10 (long-term relevance or behavioral pattern)**.

# Input

{body}

# Output

Assign high confidence scores (e.g., 8-10) only when the transcriptions provide explicit, direct evidence that {user_name} is actively engaging with the content in a meaningful way. Keep in mind that the input is what the {user_name} is viewing. It may not be what the {user_name} is actively doing, so practice caution when assigning confidence.

Return **only** JSON in the following format:

{
  "propositions": [
    {
      "proposition": "<rewritten / merged / new proposition>",
      "reasoning":   "<revised reasoning including any named entities where applicable>",
      "confidence":  <integer 1-10>,
      "decay":       <integer 1-10>
    },
    ...
  ]
}"""

# AGPT Prompts
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