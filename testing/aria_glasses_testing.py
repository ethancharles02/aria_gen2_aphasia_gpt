import os
import signal
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pydub import AudioSegment
from queue import Queue
import numpy as np

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
from agpt_lib.transcription_worker import TranscriptionWorker

class TestGlassesHandler(AriaGlassesHandler):
    def __init__(self, audio_data_queue: Queue, do_print_stats: bool):
        super().__init__()
        self.image_callback_count = 0
        self.image_callback_str = 0

        self.audio_callback_count = 0
        self.audio_callback_str = 0
        self.audio_data_bytes = []
        self.audio_data_queue = audio_data_queue
        self.num_channels = None

        self.do_print_stats = do_print_stats

    def _print_stats(self):
        if self.do_print_stats:
            print(f"Image callbacks: {self.image_callback_str}, Audio callbacks: {self.audio_callback_str}", end="\r")

    def _image_callback(self, image_data: ImageData, image_record: ImageDataRecord):
        self.image_callback_count += 1
        self.image_callback_str = f"{self.image_callback_count}, Temperature: {image_record.temperature}"
        self._print_stats()

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
        self.audio_data_queue.put(self._transform_audio_data(audio_data.data, 1))

    def _transform_audio_data(self, full_audio_data_bytes: list[int], num_output_channels: int) -> bytes:
        if self.num_channels is None:
            print("Number of channels not set, returning empty bytes")
            return bytes()

        if num_output_channels > self.num_channels:
            print("Can't increase number of channels past original")
            return bytes()

        raw_array = np.array(full_audio_data_bytes, dtype=np.int32)

        spatial_data = raw_array.reshape(-1, self.num_channels)

        d_channels = self.num_channels // num_output_channels
        leftover = self.num_channels % num_output_channels

        leftover_channel = [] if leftover == 0 else [np.mean(spatial_data[:, self.num_channels-leftover:self.num_channels], axis=1)]
        channels = [np.mean(spatial_data[:, i * d_channels:(i + 1) * d_channels], axis=1) for i in range(num_output_channels)] + leftover_channel

        # Divides by 255 since mp3 expects 16 bit but the aria stream appears to be 24 bit
        channels = tuple(map(lambda channel: (channel / 255).astype(np.int16), channels))

        output_bytes = np.column_stack(channels)

        return output_bytes.tobytes()

    def save_audio(self, filename: str):
        num_out_channels = 2
        audio_bytes = self._transform_audio_data(self.audio_data_bytes, num_out_channels)

        audio_segment = AudioSegment(
            data=audio_bytes,
            sample_width=2,
            frame_rate=AUDIO_SAMPLE_RATE,
            channels=num_out_channels
        )

        audio_segment.export(filename, format="mp3")
        print(f"Saved audio to {filename}")

def main():
    audio_data_queue = Queue()
    transcription_worker = TranscriptionWorker(audio_data_queue, WHISPER_MODEL_NAME, TRANSCRIPTION_WARMUP_SEC, PHRASE_TIMEOUT_SEC)
    transcription_worker.start_transcription_worker()

    handler = TestGlassesHandler(audio_data_queue, False)
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

    handler.save_audio("saved_audio.mp3")

if __name__ == "__main__":
    main()