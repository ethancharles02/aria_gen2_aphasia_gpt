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

import asyncio

# import Quartz
from PIL import Image

# — Local —
from .observer import Observer
from ..schemas import Update
from ..prompts.screen import TRANSCRIPTION_PROMPT, SUMMARY_PROMPT
from ..models.vision_model import VisionModel, base64_encode_image
from ..models.vision_qwen35_9b import Qwen35_9b

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
        vision_model: VisionModel = Qwen35_9b(),
        images_dir: str = "~/.cache/gum/images",
        transcription_prompt: Optional[str] = None,
        summary_prompt: Optional[str] = None,
        history_k: int = 10,
        debug: bool = False,
        api_key: str | None = None,
        api_base: str | None = None,
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

        self.transcription_prompt = transcription_prompt or TRANSCRIPTION_PROMPT
        self.summary_prompt = summary_prompt or SUMMARY_PROMPT
        self.vision_model = vision_model
        self.vision_model.setup()

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
    async def _call_vision_model(self, prompt: str, img_paths: list[str]) -> str:
        """Call Vision model to analyze images.

        Args:
            prompt (str): Prompt to guide the analysis.
            img_paths (list[str]): List of image paths to analyze.

        Returns:
            str: Vision Model's analysis of the images.
        """
        self.vision_model.set_instructions(prompt)
        # Encode all images for comparison
        if not img_paths:
            return "[no images provided]"

        encoded = await asyncio.gather(
            *[asyncio.to_thread(base64_encode_image, p) for p in img_paths]
        )

        # Try to send all images together, fall back to first image if it fails
        return self.vision_model.generate_response({}, encoded)

    # ─────────────────────────────── I/O helpers
    async def _save_frame(self, frame_path: str, tag: str) -> str:
        """Save a frame as a JPEG image.

        Args:
            frame_path (str): Path to the frame image.
            tag (str): Tag to include in the filename.

        Returns:
            str: Path to the saved image.
        """
        ts   = f"{time.time():.5f}"
        path = os.path.join(self.images_dir, f"{ts}_{tag}.jpg")
        # Copy/cache the frame, converting to RGB if needed
        def save_image():
            img = Image.open(frame_path)
            # Convert RGBA to RGB for JPEG compatibility
            if img.mode in ('RGBA', 'LA', 'P'):
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                rgb_img.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                rgb_img.save(path, "JPEG", quality=70)
            else:
                img.save(path, "JPEG", quality=70)

        await asyncio.to_thread(save_image)
        return path

    async def _process_and_emit(self, before_path: str, after_path: str) -> None:
        """Process screenshots and emit an update.

        Args:
            before_path (str): Path to the "before" screenshot.
            after_path (str | None): Path to the "after" screenshot, if any.
        """
        # chronology: append 'before' first (history order == real order)
        self._history.append(before_path)
        prev_paths = list(self._history)

        # async OpenAI calls
        try:
            transcription = await self._call_vision_model(self.transcription_prompt, [before_path, after_path])
        except Exception as exc:
            transcription = f"[transcription failed: {exc}]"

        prev_paths.append(after_path)
        try:
            summary = await self._call_vision_model(self.summary_prompt, prev_paths)
            # summary = await self._call_vision_model("Give a short summary of the differences between the images provided", prev_paths)
        except Exception as exc:
            summary = f"[summary failed: {exc}]"

        txt = (transcription + summary).strip()
        # txt = (summary).strip()
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

            ev = self._pending_event
            aft = "./testing/after.png"

            bef_path = await self._save_frame(ev["before"], "before")
            aft_path = await self._save_frame(aft, "after")
            await self._process_and_emit(bef_path, aft_path)

            self._pending_event = None

        def debounce_flush():
            """Schedule flush as a task."""
            asyncio.create_task(flush())

        async def send_data():
            # skip if we already have a pending event being processed
            # (this discards intermediate frames and keeps only the latest)
            if self._pending_event is not None:
                return

            # grab the latest frame
            async with self._frame_lock:
                bf = self._frame
            if bf is None:
                return
            self._pending_event = {"before": bf}

            # schedule debounce timer only if not already scheduled
            if not self._debounce_handle:
                self._debounce_handle = loop.call_later(DEBOUNCE, debounce_flush)

        # ---- main capture loop ----
        log.info(f"Image observer started")

        i = 0
        while self._running:                         # flag from base class
            t0 = time.time()

            async with self._frame_lock:
                self._frame = "./testing/before.png" if i % 2 == 0 else "./testing/after.png"

            await send_data()
            i += 1

            # fps throttle
            dt = time.time() - t0
            await asyncio.sleep(max(0, (1 / CAP_FPS) - dt))

        # shutdown
        if self._debounce_handle:
            self._debounce_handle.cancel()


def test_image_observer():
    import asyncio

    async def test():
        observer = ImageObserver()
        update = await observer.update_queue.get()
        print(f"\n=== UPDATE RECEIVED ===\n{update.content}\n")
        observer._running = False
        await asyncio.sleep(0.5)  # Allow worker to finish

    asyncio.run(test())