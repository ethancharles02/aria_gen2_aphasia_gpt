from __future__ import annotations
###############################################################################
# Imports                                                                     #
###############################################################################

# — Standard library —
import base64
import logging
import os
import time
from collections import deque
from typing import Optional
from openai import OpenAI

import asyncio

# — Local —
from ..imagers.imager import Imager
from ..imagers.context_generator import ContextGenerator
from ..prompts.screen import TRANSCRIPTION_PROMPT, SUMMARY_PROMPT
from ..schemas import Update
from .observer import Observer

###############################################################################
# Screen observer                                                             #
###############################################################################

class ImageObserver(Observer):
    """Observer that captures and analyzes screen content around user interactions.

    This observer captures screenshots before and after user interactions (mouse movements,
    clicks, and scrolls) and uses GPT-4 Vision to analyze the content. It can also take
    periodic screenshots and skip captures when certain applications are visible.

    Args:
        screenshots_dir (str, optional): Directory to store screenshots. Defaults to "~/.cache/gum/screenshots".
        skip_when_visible (Optional[str | list[str]], optional): Application names to skip when visible.
            Defaults to None.
        transcription_prompt (Optional[str], optional): Custom prompt for transcribing screenshots.
            Defaults to None.
        summary_prompt (Optional[str], optional): Custom prompt for summarizing screenshots.
            Defaults to None.
        model_name (str, optional): GPT model to use for vision analysis. Defaults to "gpt-4o-mini".
        history_k (int, optional): Number of recent screenshots to keep in history. Defaults to 10.
        debug (bool, optional): Enable debug logging. Defaults to False.

    Attributes:
        _CAPTURE_FPS (int): Frames per second for screen capture.
        _DEBOUNCE_SEC (int): Seconds to wait before processing an interaction.
        _MON_START (int): Index of first real display in mss.
    """

    _CAPTURE_FPS: int = 0.1
    _DEBOUNCE_SEC: int = 2
    _MON_START: int = 1     # first real display in mss

    # ─────────────────────────────── construction
    def __init__(
        self,
        vision_model: str = "qwen3.5-vision",
        imager: Imager = None,
        images_dir: str = "~/.cache/gum/images",
        transcription_prompt: str = TRANSCRIPTION_PROMPT,
        summary_prompt: str = SUMMARY_PROMPT,
        history_k: int = 10,
        debug: bool = False,
        api_key: str | None = None,
        api_base: str | None = None,
        save_images: bool = False,
        context_generators: list[ContextGenerator] = []
    ) -> None:
        """Initialize the Screen observer.

        Args:
            screenshots_dir (str, optional): Directory to store screenshots. Defaults to "~/.cache/gum/screenshots".
            skip_when_visible (Optional[str | list[str]], optional): Application names to skip when visible.
                Defaults to None.
            transcription_prompt (Optional[str], optional): Custom prompt for transcribing screenshots.
                Defaults to None.
            summary_prompt (Optional[str], optional): Custom prompt for summarizing screenshots.
                Defaults to None.
            vision_model (VisionModel, optional): Model to use for vision analysis. Defaults to "Qwen35_9b".
            history_k (int, optional): Number of recent screenshots to keep in history. Defaults to 10.
            debug (bool, optional): Enable debug logging. Defaults to False.
        """
        self.images_dir = os.path.abspath(os.path.expanduser(images_dir))
        os.makedirs(self.images_dir, exist_ok=True)

        self.transcription_prompt = transcription_prompt
        self.summary_prompt = summary_prompt
        self.vision_model = vision_model
        self.client = OpenAI(base_url=api_base, api_key=api_key)
        self.imager = imager
        self.context_generators = context_generators
        self.save_images = save_images

        self.debug = debug

        # state shared with worker
        self._frame = {}
        self._frame_lock = asyncio.Lock()

        self._history: deque[str] = deque(maxlen=max(0, history_k))
        self._pending_event: Optional[dict] = None
        self._debounce_handle: Optional[asyncio.TimerHandle] = None

        # call parent
        super().__init__()

    # ─────────────────────────────── OpenAI Vision (async)
    async def _call_vision_model(self, prompt: str, img_strs: list[str]) -> str:
        """Call Vision model to analyze images.

        Args:
            prompt (str): Prompt to guide the analysis.
            img_paths (list[str]): List of image paths to analyze.

        Returns:
            str: Vision Model's analysis of the images.
        """
        if self.client is None:
            print(f"{self.__class__.__str__}WARNING: Attempted to generate a response without setting up client first")

        if not img_strs:
            return "[no images provided]"

        content = [
            *[{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image}"}} for image in img_strs],
            {
                "type": "text",
                "text": prompt
            }
        ]

        messages = [
            {
                "role": "user",
                "content": content
            }
        ]
        chat_response = self.client.chat.completions.create(
            model=self.vision_model,
            messages=messages,
        )
        answer = chat_response.choices[0].message.content
        # TODO This isn't a valid production setup. Handle it better
        if not answer:
            raise RuntimeError("Something went wrong with the model and it didn't produce a message")
        return answer


    # ─────────────────────────────── I/O helpers
    def _save_frame(self, frame_data: str, tag: str) -> str:
        """Save a frame as a JPEG image.

        Args:
            frame_data (str): Base64 frame data
            tag (str): Tag to include in the filename.

        Returns:
            str: Path to the saved image.
        """
        ts   = f"{time.time():.5f}"
        path = os.path.join(self.images_dir, f"{ts}_{tag}.jpg")
        frame_data = base64.b64decode(frame_data)
        with open(path, "wb") as f:
            f.write(frame_data)

        return path

    async def _process_and_emit(self, before_img: str, after_img: str) -> None:
        """Process screenshots and emit an update.

        Args:
            before_img (str): Base64 "before" screenshot.
            after_img (str | None): Base64 "after" screenshot, if any.
        """
        # chronology: append 'before' first (history order == real order)
        self._history.append(before_img)
        prev_paths = list(self._history)

        transcription = ""
        # async OpenAI calls
        try:
            old_time = time.perf_counter()
            transcription = await self._call_vision_model(self.transcription_prompt, [before_img, after_img])
            print(f"Transcription time: {time.perf_counter() - old_time:0.6f} seconds")
        except Exception as exc:
            print(f"[transcription failed: {exc}]")

        prev_paths.append(after_img)

        summary = ""
        try:
            old_time = time.perf_counter()
            summary = await self._call_vision_model(self.summary_prompt, prev_paths)
            print(f"Summary time: {time.perf_counter() - old_time:0.6f} seconds")
        except Exception as exc:
            print(f"[summary failed: {exc}]")

        additional_context = []
        try:
            for ctx_generator in self.context_generators:
                additional_context.append(await ctx_generator.get_context())
        except Exception as exc:
            print(f"[Additional context generation failed: {exc}]")

        txt = f"Image Transcription: {transcription}\nImage Summary: {summary}\n{"\n".join(additional_context)}".strip()
        print(f"\n\n{txt}\n\n")
        await self.update_queue.put(Update(content=txt, content_type="input_text"))

    # ─────────────────────────────── main async worker
    async def _worker(self) -> None:          # overrides base class
        """Main worker method that captures and processes screenshots.

        This method runs in a background task and handles:
        - Mouse event monitoring
        - Screen capture
        - Periodic screenshots
        - Image processing and analysis
        """
        log = logging.getLogger("ImageObserver")
        if self.debug:
            logging.basicConfig(level=logging.INFO, format="%(asctime)s [ImageObserver] %(message)s", datefmt="%H:%M:%S")
        else:
            log.addHandler(logging.NullHandler())
            log.propagate = False

        CAP_FPS  = self._CAPTURE_FPS
        DEBOUNCE = self._DEBOUNCE_SEC

        loop = asyncio.get_running_loop()

        # ------------------------------------------------------------------
        # All calls to mss / Quartz are wrapped in `to_thread`
        # ------------------------------------------------------------------

        # ---- nested helper inside the async context ----
        async def flush():
            """Process pending event and emit update."""
            if self._pending_event is None:
                return
            # If gum is already processing a previous update for this observer, don't capture or
            # emit new images now — reschedule the flush to try again after the debounce window.
            if self.owner_processing:
                if not self._debounce_handle:
                    self._debounce_handle = loop.call_later(DEBOUNCE, debounce_flush)
                return

            ev = self._pending_event
            aft = await self.imager.get_image()

            if self.save_images:
                bef_path = self._save_frame(ev["before"], "before")
                aft_path = self._save_frame(aft, "after")
            await self._process_and_emit(ev["before"], aft)

            self._pending_event = None
            # debounce timer has fired and been flushed; clear handle so future events can schedule
            # a new debounce timer.
            self._debounce_handle = None

        def debounce_flush():
            """Schedule flush as a task."""
            asyncio.create_task(flush())

        async def send_data():
            # Skip if we already have a pending event being processed (this discards intermediate
            # frames and keeps only the latest) grab the latest frame and set pending if not already
            # set
            if self._pending_event is None:
                async with self._frame_lock:
                    bf = self._frame
                if bf is None:
                    return
                self._pending_event = {"before": bf}

            # If gum is currently processing this observer's previous update, skip scheduling new
            # flushes until it's finished.
            if self.owner_processing:
                return

            # reset debounce timer so each new frame extends the window
            if self._debounce_handle:
                try:
                    self._debounce_handle.cancel()
                except Exception:
                    pass
            self._debounce_handle = loop.call_later(DEBOUNCE, debounce_flush)

        # ---- main capture loop ----
        log.info(f"Image observer started")

        i = 0
        while self._running:
            t0 = time.time()

            # Don't capture frames while gum is processing this observer's previous update; wait and
            # loop again.
            if self.owner_processing:
                await asyncio.sleep(0.1)
                continue

            async with self._frame_lock:
                self._frame = await self.imager.get_image()

            await send_data()
            i += 1

            # fps throttle
            dt = time.time() - t0
            await asyncio.sleep(max(0, (1 / CAP_FPS) - dt))

        # shutdown
        if self._debounce_handle:
            self._debounce_handle.cancel()
            self._debounce_handle = None