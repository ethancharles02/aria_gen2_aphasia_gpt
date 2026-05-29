# Real-time phrase transcription logic adapted from:
# https://github.com/davabase/whisper_real_time/blob/master/transcribe_demo.py
# Credit: davabase (original creator).

from datetime import datetime, timedelta
from queue import Empty, Queue
import numpy as np
import threading
import time
import torch

_has_whisper = False
try:
    import whisper
    _has_whisper = True
except ImportError:
    print("Whisper is not installed; audio transcription is disabled.")

class TranscriptionWorker:
    def __init__(self, data_queue: Queue[bytes], whisper_model_name: str, warmup_time_sec: int, phrase_timeout_sec: int):
        self.whisper = None
        self.data_queue: Queue[bytes] = data_queue
        self.worker_thread: threading.Thread | None = None
        self.worker_stop_event = threading.Event()
        self.transcription_started_at = 0.0
        self.whisper_model_name = whisper_model_name
        self.warmup_time_sec = warmup_time_sec
        self.phrase_timeout_sec = phrase_timeout_sec

        global _has_whisper
        if not _has_whisper:
            return

        print(f"Loading Whisper model '{self.whisper_model_name}'...")
        self.whisper = whisper.load_model(self.whisper_model_name)
        print("Whisper model loaded.")

    def start_transcription_worker(self) -> None:
        global _has_whisper
        if not _has_whisper or (self.worker_thread is not None and self.worker_thread.is_alive()):
            return

        self.worker_stop_event.clear()
        self.transcription_started_at = time.monotonic()
        self.worker_thread = threading.Thread(target=self._transcription_worker)
        self.worker_thread.start()

    def stop_transcription_worker(self) -> None:
        self.worker_stop_event.set()
        if self.worker_thread is not None:
            self.worker_thread.join()

    # TODO research ways to isolate the voice of the person speaking (compare noise level of someone wearing the glasses compared to people nearby)
    def _transcription_worker(self) -> None:
        phrase_time = None
        phrase_bytes = bytes()
        transcription_lines = [""]

        while not self.worker_stop_event.is_set():
            if time.monotonic() - self.transcription_started_at < self.warmup_time_sec:
                while True:
                    try:
                        self.data_queue.get_nowait()
                    except Empty:
                        break
                time.sleep(0.1)
                continue

            if self.data_queue.empty():
                time.sleep(0.25)
                continue

            now = datetime.utcnow()
            phrase_complete = False
            if phrase_time and now - phrase_time > timedelta(seconds=self.phrase_timeout_sec):
                phrase_bytes = bytes()
                phrase_complete = True
            phrase_time = now

            audio_data = b"".join(self.data_queue.queue)
            self.data_queue.queue.clear()
            phrase_bytes += audio_data

            audio_np = np.frombuffer(phrase_bytes, dtype=np.int16).astype(np.float32) / 32768.0

            try:
                result = self.whisper.transcribe(
                    audio_np,
                    fp16=torch.cuda.is_available(),
                )
            except Exception as exc:
                print(f"Whisper transcription error: {exc}")
                continue

            text = result.get("text", "").strip()
            if not text:
                continue

            if phrase_complete:
                transcription_lines.append(text)
            else:
                transcription_lines[-1] = text

            print("\033c", end="")
            for line in transcription_lines:
                print(line)

            print("", end="", flush=True)