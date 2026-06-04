# Real-time phrase transcription logic adapted from:
# https://github.com/davabase/whisper_real_time/blob/master/transcribe_demo.py
# Credit: davabase (original creator).

from queue import Queue
import numpy as np
import threading
import time
import torch
import webrtcvad

_has_whisper = False
try:
    import whisper
    _has_whisper = True
except ImportError:
    print("Whisper is not installed; audio transcription is disabled.")

class TranscriptionWorker:
    def __init__(
            self,
            data_queue: Queue[bytes],
            whisper_model_name: str,
            phrase_timeout_sec: int,
            sample_rate: int,
            sr_threshold: float,
            sr_threshold_time: float,
            frame_duration_ms: int,
            start_transcription_window_s: float,
            start_transcription_threshold: float,
            do_print_transcription: bool = True
            ):
        self.whisper = None
        self.whisper_model_name = whisper_model_name
        self.data_queue: Queue[bytes] = data_queue
        self.sample_rate = sample_rate

        self.worker_thread: threading.Thread | None = None
        self.worker_stop_event = threading.Event()

        self._phrase_bytes = bytes()

        self.sr_threshold = sr_threshold
        self._sr_threshold_time = sr_threshold_time
        self._frame_duration_ms = frame_duration_ms
        # Size in bytes of one frame for speech recognition
        self._frame_size = int(self.sample_rate * (self._frame_duration_ms / 1000.0) * 2)
        # Number of frames needed to reach the threshold time
        self._threshold_size = int(self._sr_threshold_time / (self._frame_duration_ms / 1000.0))
        self._start_transcription_window_s = start_transcription_window_s
        self._start_transcription_threshold = start_transcription_threshold
        # Number of frames needed to reach the threshold time
        self._start_threshold_size = int(self._start_transcription_window_s / (self._frame_duration_ms / 1000.0))

        # Prevents transcription. Is used to prevent ill-sized samples from being fed to Whisper
        # where it can easily hallucinate
        self._enable_transcription = False

        # Each value represents if that frame has speech in it for that duration
        self.is_speech_list = []

        self.transcription_started_at = 0.0
        self.phrase_timeout_sec = phrase_timeout_sec
        self.do_print_transcription = do_print_transcription

        self._vad = webrtcvad.Vad(2)

        self._transcription_lines = [""]
        self._in_progress_phrase = ""

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

    def clear_transcription(self):
        self._transcription_lines.clear()

    def get_transcription(self):
        transcription = "\n".join(self._transcription_lines)
        return transcription

    def _update_speech_list(self) -> bool:
        current_amount = len(self.is_speech_list)
        new_amount = len(self._phrase_bytes) // self._frame_size

        if new_amount > current_amount:
            for frame_idx in range(current_amount, new_amount):
                start_byte = frame_idx * self._frame_size
                end_byte = start_byte + self._frame_size

                chunk = self._phrase_bytes[start_byte:end_byte]
                self.is_speech_list.append(self._is_speech(chunk))
            return True
        return False

    def _is_speech(self, audio_bytes: bytes):
        # TODO only use this for testing, remove when done
        frame_size = int(self.sample_rate * (self._frame_duration_ms / 1000.0) * 2)
        if len(audio_bytes) != frame_size:
            raise ValueError(f"Audio frame must be exactly {frame_size} bytes.")

        return self._vad.is_speech(audio_bytes, self.sample_rate)

    def _set_phrase_complete(self):
        self._phrase_bytes = bytes()
        phrase_to_add = self._in_progress_phrase.strip()
        if phrase_to_add:
            self._transcription_lines.append(phrase_to_add)
        self._in_progress_phrase = ""
        self.is_speech_list.clear()
        self._phrase_time = time.monotonic()
        self._enable_transcription = False

    def _get_speech_ratio(self, frames_to_look_back: int) -> float:
        """Calculate the ratio of speech frames in the last N frames."""
        if len(self.is_speech_list) < frames_to_look_back:
            return False, 0.0

        num_speech_frames = self.is_speech_list[-frames_to_look_back:].count(True)
        return True, num_speech_frames / frames_to_look_back

    def _is_above_speech_threshold(self, threshold: float, frames_to_look_back: int) -> bool:
        """Check if speech ratio is at or above threshold."""
        success, ratio = self._get_speech_ratio(frames_to_look_back)
        if not success:
            return False
        return ratio >= threshold

    def _is_below_speech_threshold(self, threshold: float, frames_to_look_back: int) -> bool:
        """Check if speech ratio is at or below threshold."""
        success, ratio = self._get_speech_ratio(frames_to_look_back)
        if not success:
            return False
        return ratio <= threshold

    # TODO research ways to isolate the voice of the person speaking (compare noise level of someone
    # wearing the glasses compared to people nearby)
    def _transcription_worker(self) -> None:
        self._phrase_time = time.monotonic()
        self._phrase_bytes = bytes()

        while not self.worker_stop_event.is_set():
            if self.data_queue.empty():
                time.sleep(0.1)
                continue

            if self.do_print_transcription:
                print("\033c", end="")
                print(self.get_transcription())
                print(self._in_progress_phrase)
                print(f"Speech packets detected: {self.is_speech_list.count(True)} / {len(self.is_speech_list)}")

                print("", end="", flush=True)

            audio_data = b"".join(self.data_queue.queue)
            self.data_queue.queue.clear()
            self._phrase_bytes += audio_data

            # If there was an update, check new window counts
            if self._update_speech_list():
                if self._is_below_speech_threshold(1 - self.sr_threshold, self._threshold_size):
                    self._set_phrase_complete()
                    continue

                if not self._enable_transcription and self._is_above_speech_threshold(self._start_transcription_threshold, self._start_threshold_size):
                    self._enable_transcription = True

            if self._enable_transcription:
                audio_np = np.frombuffer(self._phrase_bytes, dtype=np.int16).astype(np.float32) / 32768.0

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

                self._in_progress_phrase = text

            # Forces a completion if the timeout is reached
            if self._phrase_time and time.monotonic() - self._phrase_time > self.phrase_timeout_sec:
                self._set_phrase_complete()