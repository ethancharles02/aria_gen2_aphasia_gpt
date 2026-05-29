import sys
import os
import signal
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from projectaria_tools.core.sensor_data import (
    AudioData,
    AudioDataRecord,
    ImageData,
    ImageDataRecord,
)

# For local secret variables
from agpt_lib.aria_glasses_handler import AriaGlassesHandler
from agpt_lib.agpt_prompts import *
from agpt_lib.agpt_secrets import *
from agpt_lib.aphasia_config import *

class TestGlassesHandler(AriaGlassesHandler):
    def __init__(self):
        super().__init__()
        self.image_callback_count = 0
        self.image_callback_str = 0

        self.audio_callback_count = 0
        self.audio_callback_str = 0

    def _print_stats(self):
        print(f"Image callbacks: {self.image_callback_str}, Audio callbacks: {self.audio_callback_str}", end="\r")

    def _image_callback(self, image_data: ImageData, image_record: ImageDataRecord):
        self.image_callback_count += 1
        self.image_callback_str = f"{self.image_callback_count}, Temperature: {image_record.temperature}"
        self._print_stats()

    def _audio_callback(self, audio_data: AudioData, audio_record: AudioDataRecord, num_channels: int):
        self.audio_callback_count += 1
        self.audio_callback_str = f"{self.audio_callback_count}"
        self._print_stats()

def main():
    handler = TestGlassesHandler()
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

if __name__ == "__main__":
    main()