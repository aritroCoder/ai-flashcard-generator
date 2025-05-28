from openai import OpenAI, AzureOpenAI
from dotenv import load_dotenv
import os
from utils import download_lecture, get_audio_transcript
from langchain_community.document_loaders import UnstructuredPDFLoader
import json
import time

start_time = time.time()

load_dotenv()
platform = os.environ.get("PLATFORM")
speech_client = None
chat_client = None
speech_model = None
chat_model = None

if platform == "azure":
    speech_base = os.environ.get("AZURE_SPEECH_BASE")
    speech_api_key = os.environ.get("AZURE_SPEECH_API_KEY")
    speech_version = os.environ.get("AZURE_SPEECH_VERSION")
    speech_model = os.environ.get("SPEECH_MODEL")

    chat_base = os.environ.get("AZURE_OPEN_API_BASE")
    chat_key = os.environ.get("AZURE_OPENAI_API_KEY")
    chat_version = os.environ.get("AZURE_CHAT_VERSION")
    chat_model = os.environ.get("CHAT_MODEL")

    if not speech_base or not speech_api_key or not speech_version or not speech_model:
        raise ValueError(
            "Please set AZURE_SPEECH_BASE, AZURE_SPEECH_API_KEY, AZURE_SPEECH_VERSION, and SPEECH_MODEL in your environment variables."
        )
    speech_client = AzureOpenAI(
        api_version=speech_version,
        api_key=speech_api_key,
        azure_endpoint=speech_base,
    )

    if not chat_base or not chat_key or not chat_version or not chat_model:
        raise ValueError(
            "Please set AZURE_OPEN_API_BASE, AZURE_OPEN_API_KEY, AZURE_OPEN_API_VERSION, and CHAT_MODEL in your environment variables."
        )
    chat_client = AzureOpenAI(
        api_version=chat_version,
        api_key=chat_key,
        base_url=chat_base,
    )
elif platform == "litellm":
    api_key = os.environ.get("LITELLM_API_KEY")
    base_url = os.environ.get("LITELLM_PROXY_URL")
    speech_model = os.environ.get("LITELLM_SPEECH_MODEL")
    chat_model = os.environ.get("LITELLM_CHAT_MODEL")
    if not api_key or not base_url:
        raise ValueError(
            "Please set LITELLM_API_KEY and LITELLM_PROXY_URL in your environment variables."
        )
    speech_client = OpenAI(
        api_key=api_key,
        base_url=base_url,
    )
    chat_client = OpenAI(
        api_key=api_key,
        base_url=base_url,
    )

download_lecture(
    save_path="video",
    link="https://dysg3c97clm9i.cloudfront.net/88e2f03c-4ec2-42ff-8cf5-33452cfab4c6/mp4_muxing/88e2f03c-4ec2-42ff-8cf5-33452cfab4c6_720p.mp4",
    filename="vid1.mp4",
)

if speech_client is None:
    raise ValueError(
        "No client is configured. Please check your environment variables."
    )
if speech_model is None:
    raise ValueError(
        "No speech model is configured. Please check your environment variables."
    )

'''
Generate transcript from the video file using the speech client
'''
transcript = get_audio_transcript(
    video_path="video/vid1.mp4",
    audio_folder="audio",
    audiofile="vid1",
    client=speech_client,
    model=speech_model,
    verbose=False,
)

'''
Save the generated transcript to a file
'''
transcript_file = "transcript.txt"
with open(transcript_file, "w", encoding="utf-8") as f:
    if isinstance(transcript, dict):
        f.write(json.dumps(transcript, ensure_ascii=False, indent=2))
    else:
        f.write(transcript)

'''load transcript from file if already generated'''
# transcript_file = "transcript.txt"
# if os.path.exists(transcript_file):
#     with open(transcript_file, "r", encoding="utf-8") as f:
#         transcript = f.read()
# else:
#     raise FileNotFoundError(
#         f"Transcript file {transcript_file} not found. Please generate the transcript first."
#     )

lecture_notes_file = "lecture_notes/vid1.pdf"

loader = UnstructuredPDFLoader(lecture_notes_file)
documents = loader.load()

all_text = "".join(
    doc.page_content
    .replace("\n", "")
    .replace("\r", "")
    .replace("\t", "")
    for doc in documents
)
notes_file = "notes.txt"
with open(notes_file, "w", encoding="utf-8") as f:
    f.write(all_text)


# generate flashcards using chat client
def generate_flashcards(
    notes: str, client: AzureOpenAI | OpenAI, model: str, transcript: str
):
    function = {
        "name": "generate_flashcards",
        "description": "Generate 10 flashcards with concept and question cards. Concepts should have student friendly explanations. *Always* use latex for mathematical expressions, chemical equations or other relevant things.",
        "parameters": {
            "type": "object",
            "properties": {
                "flashcards": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "concept_card": {
                                "type": "object",
                                "properties": {
                                    "concept": {"type": "string"},
                                    "explanation": {"type": "string"},
                                },
                                "required": ["concept"],
                            },
                            "question_card": {
                                "type": "object",
                                "properties": {
                                    "question": {"type": "string"},
                                    "options": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "correct_option": {"type": "string"},
                                },
                                "required": ["question", "options", "correct_option"],
                            },
                        },
                        "required": ["concept_card", "question_card"],
                    },
                }
            },
            "required": ["flashcards"],
        },
    }

    prompt = f"""Generate 10 flashcards from the lecture below. There are two types of flashcards: 
1. concept_card - explains a core idea for student friendly revision, *Always* use latex for mathematical expressions, chemical equations or other relevant things. 
2. question_card - asks a quiz-style question with an answer. Questions should be multiple choice with 4 options, and the correct answer should be included. Options should directly contain the option without any serial number (like 1,2,3,4 or A,B,C,D). Correct option should be one of the option numbers (1, 2, 3, or 4).

Lecture transcript: {transcript}
Lecture notes: {notes}"""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        functions=[function], # type: ignore
        function_call={"name": "generate_flashcards"},
        temperature=0.3
    )

    return response.choices[0].message.function_call


if chat_client is None:
    raise ValueError(
        "No chat client is configured. Please check your environment variables."
    )
if chat_model is None:
    raise ValueError(
        "No chat model is configured. Please check your environment variables."
    )

if not isinstance(transcript, str):
    raise TypeError(
        "Transcript must be a string. Got type: " + type(transcript).__name__
    )

flashcards = generate_flashcards(
    notes=all_text,
    client=chat_client,
    model=chat_model,
    transcript=transcript,
)
# parse the flashcards from the response
if flashcards is None:
    raise ValueError("Failed to generate flashcards")

try:
    flashcards = json.loads(flashcards.arguments)
except json.JSONDecodeError as e:
    print("Error parsing flashcards JSON:", e)
    raise ValueError("The response from the chat model is not valid JSON.")

# Save flashcards to a file
flashcards_file = "flashcards.json"
with open(flashcards_file, "w", encoding="utf-8") as f:
    json.dump(flashcards, f, ensure_ascii=False, indent=2)
print(f"Flashcards saved to {flashcards_file}")

end_time = time.time()
elapsed = end_time - start_time
print(f"Total execution time: {elapsed:.2f} seconds")
