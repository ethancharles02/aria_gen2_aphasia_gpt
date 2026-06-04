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
            # TODO commented lines aren't functional due to some problems with the transcription
            # worker deciding when to end phrases. That fix will come in the next patch
            # self._current_transcription = "\n".join(self.transcription_worker.get_transcription())
            self._current_transcription = self.transcription_worker._in_progress_phrase
            # self.transcription_worker.clear_transcription()
            return f"Audio Transcription: {self._current_transcription}"