"""
Transcription context generator - generates transcription context from the existing transcription worker.
"""

import asyncio

from .transcription_worker import TranscriptionWorker

class TranscriptionContextGenerator:
    """Generates transcription context by querying the transcription worker.
    """

    def __init__(self, transcription_worker: TranscriptionWorker):
        self.transcription_worker = transcription_worker
        self._lock = asyncio.Lock()

    async def get_context(self) -> str:
        """Gets the current transcription as context.

        Returns:
            str -- Current transcription text
        """
        async with self._lock:
            self._current_transcription = f"{self.transcription_worker.get_transcription()}\n{self.transcription_worker._in_progress_phrase}"
            self.transcription_worker.clear_transcription()
            return f"Audio Transcription: {self._current_transcription}"