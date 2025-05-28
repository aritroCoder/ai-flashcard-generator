from typing import Literal
from pytubefix import YouTube
from moviepy import VideoFileClip
from pydub import AudioSegment
from openai import AzureOpenAI, OpenAI
from openai.types.audio import TranscriptionVerbose
import os
import time
import random
import requests


def download_lecture(save_path, link, filename=None, source: Literal["youtube", "direct"] = "direct"):
    if source == "youtube":
        yt = YouTube(link)
        stream = yt.streams.filter(progressive=True, file_extension="mp4").order_by(
            "resolution"
        ).desc().first()
        if stream:
            stream.download(output_path=save_path, filename=filename)
            print("Video downloaded successfully!")
        else:
            print("No suitable video stream found.")
    elif source == "direct":
        if not filename:
            raise ValueError("Filename must be provided for direct downloads.")
        os.makedirs(save_path, exist_ok=True)
        file_path = os.path.join(save_path, filename)
        if not os.path.exists(file_path):
            response = requests.get(link)
            with open(file_path, "wb") as file:
                file.write(response.content)
            print("Video downloaded successfully!")
        else:
            print(f"File {filename} already exists in {save_path}.")


def get_audio_transcript(
    video_path: str, audio_folder: str, audiofile: str, client: AzureOpenAI | OpenAI, model: str, verbose=False, s=0, lang="en"
):
    # Load the video clip
    video_clip = VideoFileClip(video_path)

    # Extract the audio from the video clip
    audio_clip = video_clip.audio

    # Write the audio to a separate file
    os.makedirs(audio_folder, exist_ok=True)
    audio_file_path = os.path.join(audio_folder, f"{audiofile}.mp3")
    if audio_clip is not None:
        audio_clip.write_audiofile(audio_file_path)
        audio_clip.close()
    else:
        raise ValueError(f"No audio track found in video: {video_path}")

    # Close the video clip
    video_clip.close()

    # Load audio with pydub
    audio = AudioSegment.from_file(audio_file_path)

    # Split audio into chunks if larger than 25 MB
    chunk_size_ms = 5 * 60 * 1000  # 5 minutes in milliseconds
    chunks = [audio[i : i + chunk_size_ms] for i in range(0, len(audio), chunk_size_ms)]

    transcriptions: list[TranscriptionVerbose | str] = []
    offset = 0

    '''
    Idea behind this weird prompt is to make the model behave like a human who is thinking out loud, in hinglish. STT models often struggle with hinglish or code mixed english hindi texts, so this prompt is used to explicitly tell the model to behave and think like a human.
    '''
    whisper_prompt = (
        "Umm, mujhe sochne do, hmm... Thik hai, yeh hai jo main, jaise, soch raha hoon."
    )
    for i, chunk in enumerate(chunks):
        print(f"Transcript: Working on chunk {i+1}/{len(chunks)}")
        chunk_path = os.path.join(
            audio_folder, f"{audiofile}_segment_{s}_chunk_{i}.mp3"
        )
        chunk.export(chunk_path, format="mp3")

        with open(chunk_path, "rb") as audio_file:
            audio_too_short = False
            while True:
                try:
                    if verbose:
                        transcription = client.audio.transcriptions.create(
                            model=model,
                            file=audio_file,
                            language=lang,
                            response_format="verbose_json",
                            timestamp_granularities=["segment"],
                            prompt=whisper_prompt,
                        )

                        if transcription.segments is not None:
                            for segment in transcription.segments:
                                segment.start += offset
                                segment.end += offset

                        transcriptions.append(transcription)
                    else:
                        transcription = client.audio.transcriptions.create(
                            model=model,
                            file=audio_file,
                            language=lang,
                            prompt=whisper_prompt,
                        )
                        transcriptions.append(transcription.text)
                    whisper_prompt = transcription.text
                    break
                except Exception as e:
                    status_code = getattr(e, "status_code", None)
                    print(
                        f"Message from chunk {i+1}: {e}\nStatus of message: {status_code}"
                    )
                    if status_code is not None and 500 <= status_code < 600:
                        print(
                            f"Retrying due to server error {status_code} on chunk {i+1}"
                        )
                        time.sleep(5)
                        continue
                    elif status_code == 429:
                        sleep_dur = random.randint(31, 60)
                        print(
                            f"Rate limit exceeded, waiting for a {sleep_dur} seconds on chunk {i+1}..."
                        )
                        time.sleep(sleep_dur)
                        continue
                    else:
                        print(
                            f"Short audio on chunk {i+1}. Error code: {status_code}"
                        )
                        audio_too_short = True
                        break
            if audio_too_short:
                continue
        offset += len(chunk) / 1000

    if verbose and not all(isinstance(item, str) for item in transcriptions):
        combined_transcription = {
            "segments": [ts_seg.segments for ts_seg in transcriptions if not isinstance(ts_seg, str)],
        }
        return combined_transcription
    else:
        combined_text = "\n".join([ts for ts in transcriptions if isinstance(ts, str)])
        return combined_text