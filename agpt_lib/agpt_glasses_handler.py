from queue import Queue
import asyncio
import base64
import cv2

from projectaria_tools.core.mps import EyeGaze
from projectaria_tools.core.sensor_data import (
    AudioData,
    AudioDataRecord,
    ImageData,
    ImageDataRecord,
)

from .agpt_config import *
from .aria_glasses_handler import AriaGlassesHandler
from .aria_helpers import transform_audio_data, project_eyegaze

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

        self._do_image_callback = True
        self._do_audio_callback = True
        self._do_eyegaze_callback = True

        # Eyegaze stuff
        self._streaming_manager = None
        self._last_et_pixel = []
        self._last_et_timestamp_s = None

    def _get_image_mat(self, image_data: ImageData, image_record: ImageDataRecord):
        img_arr = image_data.to_numpy_array()
        img_mat = cv2.cvtColor(img_arr, cv2.COLOR_RGB2BGR)
        if self._last_et_timestamp_s is not None:
            # Check if they are within the threshold of time
            if image_record.capture_timestamp_ns / 1000 - self._last_et_timestamp_s * 1_000_000 < 1000 * EYEGAZE_THRESHOLD_TIME:
                cv2.circle(img_mat, (int(self._last_et_pixel[0]), int(self._last_et_pixel[1])), EYEGAZE_RADIUS, EYEGAZE_COLOR, -1)

        return img_mat

    def _image_callback(self, image_data: ImageData, image_record: ImageDataRecord):
        img_mat = None

        if self.show_live_stream:
            img_mat = self._get_image_mat(image_data, image_record)
            cv2.imshow("Live View", img_mat)
            cv2.waitKey(1)

        if not self.image_request_queue.empty():
            if img_mat is None:
                img_mat = self._get_image_mat(image_data, image_record)

            success, encoded_image = cv2.imencode(".jpg", img_mat, [cv2.IMWRITE_JPEG_QUALITY, 95])
            if not success:
                raise RuntimeError("Failed to encode image")
            base64_str = base64.b64encode(encoded_image).decode()

            async def update_queues():
                await self.image_request_queue.get()
                await self.image_data_queue.put(base64_str)

            asyncio.run_coroutine_threadsafe(update_queues(), self.event_loop)

    def _eyegaze_callback(self, eyegaze_data: EyeGaze):
        # Get the projected coordinates of the eye gaze point on the image
        maybe_pixel = project_eyegaze(eyegaze_data, self._device_calibration)

        if maybe_pixel is not None:
            self._last_et_pixel = maybe_pixel
            self._last_et_timestamp_s = eyegaze_data.tracking_timestamp.total_seconds()

    def _audio_callback(self, audio_data: AudioData, audio_record: AudioDataRecord, num_channels: int):
        if self.num_audio_channels is None:
            self.num_audio_channels = num_channels

        if self.num_audio_channels != num_channels:
            print(f"WARNING: audio data received in inconsistent number of channels (Set {self.num_audio_channels} but received {num_channels})")

        # Add single channel audio data to queue
        self.audio_data_queue.put(transform_audio_data(self.num_audio_channels, audio_data.data, 1))
