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

from .agpt_config import *
from .aria_glasses_handler import AriaGlassesHandler

class AgptGlassesHandler(AriaGlassesHandler):
    def __init__(
            self,
            show_live_stream: bool,
            image_request_queue: asyncio.Queue,
            image_data_queue: asyncio.Queue,
            event_loop: asyncio.AbstractEventLoop,
            audio_data_queue: Queue[bytes],
            audio_sample_rate: int):
        super().__init__()
        self.show_live_stream: bool = show_live_stream
        self.image_request_queue: asyncio.Queue = image_request_queue
        self.image_data_queue: asyncio.Queue = image_data_queue
        self.event_loop: asyncio.AbstractEventLoop = event_loop
        self.audio_data_queue: Queue[bytes] = audio_data_queue
        self.audio_sample_rate = audio_sample_rate
        self.num_audio_channels = None

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
        if self.num_audio_channels is None:
            self.num_audio_channels = num_channels

        if self.num_audio_channels != num_channels:
            print(f"WARNING: audio data received in inconsistent number of channels (Set {self.num_audio_channels} but received {num_channels})")

        # Add single channel audio data to queue
        self.audio_data_queue.put(self._transform_audio_data(audio_data.data, 1))

    def _transform_audio_data(self, full_audio_data_bytes: list[int], num_output_channels: int) -> bytes:
        if self.num_audio_channels is None:
            print("Number of channels not set, returning empty bytes")
            return bytes()

        if num_output_channels > self.num_audio_channels:
            print("Can't increase number of channels past original")
            return bytes()

        raw_array = np.array(full_audio_data_bytes, dtype=np.int32)

        spatial_data = raw_array.reshape(-1, self.num_audio_channels)

        d_channels = self.num_audio_channels // num_output_channels
        leftover = self.num_audio_channels % num_output_channels

        leftover_channel = [] if leftover == 0 else [np.mean(spatial_data[:, self.num_audio_channels-leftover:self.num_audio_channels], axis=1)]
        channels = [np.mean(spatial_data[:, i * d_channels:(i + 1) * d_channels], axis=1) for i in range(num_output_channels)] + leftover_channel

        # Divides by 255 since whisper expects 16 bit but the aria stream appears to be 24 bit
        channels = tuple(map(lambda channel: (channel / 255).astype(np.int16), channels))

        output_bytes = np.column_stack(channels)

        return output_bytes.tobytes()