from queue import Queue
import asyncio
import base64
import cv2
import numpy as np

from projectaria_tools.core.mps import EyeGaze
from projectaria_tools.core.sensor_data import (
    AudioData,
    AudioDataRecord,
    ImageData,
    ImageDataRecord,
)

from .aria_glasses_handler import AriaGlassesHandler

class AgptGlassesHandler(AriaGlassesHandler):
    def __init__(
            self,
            show_live_stream: bool,
            image_request_queue: asyncio.Queue,
            image_data_queue: asyncio.Queue,
            event_loop: asyncio.AbstractEventLoop,
            audio_data_queue: Queue[bytes],
            default_audio_sample_rate: int,
            whisper_sample_rate: int):
        super().__init__()
        self.show_live_stream: bool = show_live_stream
        self.image_request_queue: asyncio.Queue = image_request_queue
        self.image_data_queue: asyncio.Queue = image_data_queue
        self.event_loop: asyncio.AbstractEventLoop = event_loop
        self.audio_data_queue: Queue[bytes] = audio_data_queue
        self.whisper_sample_rate = whisper_sample_rate
        self.default_audio_sample_rate = default_audio_sample_rate

    def _image_callback(self, image_data: ImageData, image_record: ImageDataRecord):
        img_arr = None
        bgr_img = None

        if self.show_live_stream:
            img_arr = image_data.to_numpy_array()
            bgr_img = cv2.cvtColor(img_arr, cv2.COLOR_RGB2BGR)
            cv2.imshow("Live View", bgr_img)
            cv2.waitKey(1)

        if not self.image_request_queue.empty():
            if bgr_img is None:
                img_arr = image_data.to_numpy_array()
                bgr_img = cv2.cvtColor(img_arr, cv2.COLOR_RGB2BGR)

            success, encoded_image = cv2.imencode(".jpg", bgr_img, [cv2.IMWRITE_JPEG_QUALITY, 95])
            if not success:
                raise RuntimeError("Failed to encode image")
            base64_str = base64.b64encode(encoded_image).decode()

            async def update_queues():
                await self.image_request_queue.get()
                await self.image_data_queue.put(base64_str)

            asyncio.run_coroutine_threadsafe(update_queues(), self.event_loop)

    def eyegaze_callback(self, eyegaze_data: EyeGaze):
        pass
        # global old_time
        # # Only updates every second
        # if time.monotonic() - old_time > 1:
        #     if eyegaze_data.depth != 0:
        #         print(
        #             f"Received EyeGaze data at timestamp {eyegaze_data.tracking_timestamp.total_seconds()} sec "
        #             f"with yaw={eyegaze_data.yaw:.3f} rad, pitch={eyegaze_data.pitch:.3f} rad, "
        #             f"depth={eyegaze_data.depth:.3f} m"
        #         )
        #     else:
        #         print("Eyegaze not detected")

    def _audio_callback(self, audio_data: AudioData, audio_record: AudioDataRecord, num_channels: int):
        raw_samples = np.asarray(audio_data.data, dtype=np.float32)
        if raw_samples.size == 0:
            return

        normalized = raw_samples.astype(np.float32, copy=False)

        if num_channels > 1 and normalized.size % num_channels == 0:
            normalized = normalized.reshape(-1, num_channels)[:, 0]

        peak = float(np.max(np.abs(normalized))) if normalized.size else 0.0
        if peak <= 0:
            return
        normalized = normalized / peak

        source_sample_rate_hz = self._estimate_sample_rate_hz(audio_record.capture_timestamps_ns)
        chunk_16k = self._resample_audio(normalized, source_sample_rate_hz)
        if chunk_16k.size > 0:
            chunk_i16 = np.clip(chunk_16k, -1.0, 1.0)
            chunk_i16 = (chunk_i16 * 32767.0).astype(np.int16)
            # Send data to the transcription worker
            self.audio_data_queue.put(chunk_i16.tobytes())

    def _estimate_sample_rate_hz(self, capture_timestamps_ns: list[int]) -> int:
        if len(capture_timestamps_ns) < 2:
            return self.default_audio_sample_rate

        timestamps = np.asarray(capture_timestamps_ns, dtype=np.int64)
        deltas = np.diff(timestamps)
        deltas = deltas[deltas > 0]
        if deltas.size == 0:
            return self.default_audio_sample_rate

        estimated_rate = int(round(1e9 / float(np.median(deltas))))
        if estimated_rate < 8000 or estimated_rate > 96000:
            return self.default_audio_sample_rate
        return estimated_rate

    def _resample_audio(self, audio: np.ndarray, source_sample_rate_hz: int) -> np.ndarray:
        if audio.size == 0:
            return audio
        if source_sample_rate_hz == self.whisper_sample_rate:
            return audio.astype(np.float32, copy=False)

        source_num_samples = audio.shape[0]
        target_num_samples = int(round(source_num_samples * self.whisper_sample_rate / source_sample_rate_hz))
        if target_num_samples <= 1:
            return np.array([], dtype=np.float32)

        source_positions = np.linspace(0, source_num_samples - 1, num=source_num_samples)
        target_positions = np.linspace(0, source_num_samples - 1, num=target_num_samples)
        return np.interp(target_positions, source_positions, audio).astype(np.float32)