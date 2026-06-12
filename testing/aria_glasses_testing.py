import os
import signal
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pydub import AudioSegment
from queue import Queue
import cv2

from projectaria_tools.core.mps import EyeGaze
from projectaria_tools.core.sensor_data import (
    AudioData,
    AudioDataRecord,
    ImageData,
    ImageDataRecord,
)

# For local secret variables
from agpt_lib.agpt_config import *
from agpt_lib.agpt_prompts import *
from agpt_lib.agpt_secrets import *
from agpt_lib.aria_glasses_handler import AriaGlassesHandler
from agpt_lib.aria_helpers import transform_audio_data, project_eyegaze, save_audio
from agpt_lib.transcription_worker import TranscriptionWorker

class TestGlassesHandler(AriaGlassesHandler):
    def __init__(
            self,
            audio_data_queue: Queue,
            do_print_stats: bool,
            show_live_stream: bool,
            do_image_callback: bool = True,
            do_audio_callback: bool = True,
            do_eyegaze_callback: bool = True):
        super().__init__()
        self.image_callback_count = 0
        self.image_callback_str = 0

        self.audio_callback_count = 0
        self.audio_callback_str = 0
        self.audio_data_bytes = []
        self.audio_data_queue = audio_data_queue
        self.num_channels = None

        self.do_print_stats = do_print_stats
        self.show_live_stream = show_live_stream

        self._do_image_callback = do_image_callback
        self._do_audio_callback = do_audio_callback
        self._do_eyegaze_callback = do_eyegaze_callback

        # Eyegaze stuff
        self._streaming_manager = None
        self._last_et_pixel = []
        self._last_et_timestamp_s = None

    def _print_stats(self):
        if self.do_print_stats:
            print(f"Image callbacks: {self.image_callback_str}, Audio callbacks: {self.audio_callback_str}", end="\r")

    def _image_callback(self, image_data: ImageData, image_record: ImageDataRecord):
        self.image_callback_count += 1
        self.image_callback_str = f"{self.image_callback_count}, Temperature: {image_record.temperature}"
        self._print_stats()

        img_arr = None
        bgr_img = None

        if self.show_live_stream:
            img_arr = image_data.to_numpy_array()
            bgr_img = cv2.cvtColor(img_arr, cv2.COLOR_RGB2BGR)
            if self._last_et_timestamp_s is not None:
                # Check if they are within the threshold of each other
                if image_record.capture_timestamp_ns / 1000 - self._last_et_timestamp_s * 1_000_000 < 1000 * EYEGAZE_THRESHOLD_TIME:
                    cv2.circle(bgr_img, (int(self._last_et_pixel[0]), int(self._last_et_pixel[1])), EYEGAZE_RADIUS, EYEGAZE_COLOR, -1)
            cv2.imshow("Live View", bgr_img)
            cv2.waitKey(1)

    def _audio_callback(self, audio_data: AudioData, audio_record: AudioDataRecord, num_channels: int):
        if self.num_channels is None:
            self.num_channels = num_channels

        if self.num_channels != num_channels:
            print(f"WARNING: audio data received in inconsistent number of channels (Set {self.num_channels} but received {num_channels})")

        self.audio_callback_count += 1
        self.audio_callback_str = f"{self.audio_callback_count}"
        self._print_stats()

        self.audio_data_bytes += audio_data.data
        # Add single channel audio data to queue
        self.audio_data_queue.put(transform_audio_data(self.num_channels, audio_data.data, 1))

    def _eyegaze_callback(self, eyegaze_data: EyeGaze):
        # Get the projected coordinates of the eye gaze point on the image
        maybe_pixel = project_eyegaze(eyegaze_data, self._device_calibration)

        if maybe_pixel is not None:
            self._last_et_pixel = maybe_pixel
            self._last_et_timestamp_s = eyegaze_data.tracking_timestamp.total_seconds()

def main():
    audio_data_queue = Queue()
    transcription_worker = TranscriptionWorker(
        audio_data_queue,
        WHISPER_MODEL_NAME,
        PHRASE_TIMEOUT_SEC,
        AUDIO_SAMPLE_RATE,
        SR_THRESHOLD,
        SR_THRESHOLD_TIME,
        FRAME_DURATION_MS,
        VAD_SPEECH_THRESHOLD,
        START_TRANSCRIPTION_WINDOW_S,
        START_TRANSCRIPTION_THRESHOLD,
        True,
        True
        )
    transcription_worker.start_transcription_worker()

    handler = TestGlassesHandler(audio_data_queue, False, False)
    handler.setup_device(DEVICE_IP, INITIAL_CONNECTION_OVER_WIFI, STREAM_CONFIG_NAME, STREAM_BATCH_PERIOD_MS, STREAMING_IP, STREAM_OVER_WIFI)
    handler.setup_streaming_receiver("", "0.0.0.0", 6768)

    handler.start_device_streaming()
    handler.start_streaming_receiver()
    handler.start_temperature_monitor(False)

    print("Streaming... Press Ctrl+C to stop")
    try:
        signal.pause()
    except KeyboardInterrupt:
        pass

    handler.stop_temperature_monitor()
    print("Shutting down streaming")
    handler.stop_streaming_receiver()
    handler.stop_device_streaming()
    print("Streaming stopped")

    transcription_worker.stop_transcription_worker()

    print("Transcription:")
    for line in transcription_worker._transcription_lines:
        print(line)

    num_out_channels = 1
    audio_bytes = transform_audio_data(handler.num_channels, handler.audio_data_bytes, num_out_channels)
    save_audio("saved_audio.mp3", audio_bytes, num_out_channels, AUDIO_SAMPLE_RATE)

if __name__ == "__main__":
    main()