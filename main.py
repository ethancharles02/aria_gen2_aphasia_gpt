#!/usr/bin/env python3

# WARNING: Requires Aria Gen 2 Client-SDK to be installed (see
# https://facebookresearch.github.io/projectaria_tools/gen2/ark/client-sdk/start)

# Real-time phrase transcription logic adapted from:
# https://github.com/davabase/whisper_real_time/blob/master/transcribe_demo.py
# Credit: davabase (original creator).

from datetime import datetime, timedelta
from queue import Empty, Queue
import numpy as np
import threading
import time
import torch

import aria.stream_receiver as receiver
import aria.sdk_gen2 as sdk_gen2
from projectaria_tools.core.mps import EyeGaze
from projectaria_tools.core.sensor_data import (
    AudioData,
    AudioDataRecord,
    ImageData,
    ImageDataRecord,
)

# For local secret variables
from agpt_lib.secrets import *
from agpt_lib.aphasia_config import *

device_client = sdk_gen2.DeviceClient()

_whisper = None
_data_queue: Queue[bytes] = Queue()
_worker_thread: threading.Thread | None = None
_worker_stop_event = threading.Event()
_transcription_started_at = 0.0

def init_whisper_model() -> None:
    global _whisper
    try:
        import whisper
    except ImportError:
        print("Whisper is not installed; audio transcription is disabled.")
        _whisper = None
        return

    print(f"Loading Whisper model '{WHISPER_MODEL_NAME}'...")
    _whisper = whisper.load_model(WHISPER_MODEL_NAME)
    print("Whisper model loaded.")

def estimate_sample_rate_hz(capture_timestamps_ns: list[int]) -> int:
    if len(capture_timestamps_ns) < 2:
        return DEFAULT_AUDIO_SAMPLE_RATE

    timestamps = np.asarray(capture_timestamps_ns, dtype=np.int64)
    deltas = np.diff(timestamps)
    deltas = deltas[deltas > 0]
    if deltas.size == 0:
        return DEFAULT_AUDIO_SAMPLE_RATE

    estimated_rate = int(round(1e9 / float(np.median(deltas))))
    if estimated_rate < 8000 or estimated_rate > 96000:
        return DEFAULT_AUDIO_SAMPLE_RATE
    return estimated_rate

def resample_audio(audio: np.ndarray, source_sample_rate_hz: int) -> np.ndarray:
    if audio.size == 0:
        return audio
    if source_sample_rate_hz == WHISPER_SAMPLE_RATE:
        return audio.astype(np.float32, copy=False)

    source_num_samples = audio.shape[0]
    target_num_samples = int(round(source_num_samples * WHISPER_SAMPLE_RATE / source_sample_rate_hz))
    if target_num_samples <= 1:
        return np.array([], dtype=np.float32)

    source_positions = np.linspace(0, source_num_samples - 1, num=source_num_samples)
    target_positions = np.linspace(0, source_num_samples - 1, num=target_num_samples)
    return np.interp(target_positions, source_positions, audio).astype(np.float32)

def start_transcription_worker() -> None:
    global _worker_thread, _transcription_started_at
    if _whisper is None or (_worker_thread is not None and _worker_thread.is_alive()):
        return

    _worker_stop_event.clear()
    _transcription_started_at = time.monotonic()
    _worker_thread = threading.Thread(target=transcription_worker)
    _worker_thread.start()

def stop_transcription_worker() -> None:
    _worker_stop_event.set()
    if _worker_thread is not None:
        _worker_thread.join()

def transcription_worker() -> None:
    phrase_time = None
    phrase_bytes = bytes()
    transcription_lines = [""]

    while not _worker_stop_event.is_set():
        if time.monotonic() - _transcription_started_at < TRANSCRIPTION_WARMUP_SEC:
            while True:
                try:
                    _data_queue.get_nowait()
                except Empty:
                    break
            time.sleep(0.1)
            continue

        if _data_queue.empty():
            time.sleep(0.25)
            continue

        now = datetime.utcnow()
        phrase_complete = False
        if phrase_time and now - phrase_time > timedelta(seconds=PHRASE_TIMEOUT_SEC):
            phrase_bytes = bytes()
            phrase_complete = True
        phrase_time = now

        audio_data = b"".join(_data_queue.queue)
        _data_queue.queue.clear()
        phrase_bytes += audio_data

        audio_np = np.frombuffer(phrase_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        try:
            result = _whisper.transcribe(
                audio_np,
                fp16=torch.cuda.is_available(),
            )
        except Exception as exc:
            print(f"Whisper transcription error: {exc}")
            continue

        text = result.get("text", "").strip()
        if not text:
            continue

        if phrase_complete:
            transcription_lines.append(text)
        else:
            transcription_lines[-1] = text

        print("\033c", end="")
        for line in transcription_lines:
            print(line)

        print("", end="", flush=True)

def device_streaming() -> sdk_gen2.Device:
    # Set up the device client config to specify the device to be connected to e.g. device serial
    # number. If nothing is specified, the first device in the list of connected devices will be
    # connected to
    config = sdk_gen2.DeviceClientConfig()
    device_client.set_client_config(config)
    device = device_client.connect()

    # Set recording config with profile name
    streaming_config = sdk_gen2.HttpStreamingConfig()

    if STREAM_CONFIG_NAME.endswith(".json"):
        streaming_config.profile_json = STREAM_CONFIG_NAME
    else:
        streaming_config.profile_name = STREAM_CONFIG_NAME

    if STREAM_OVER_WIFI:
        print("Streaming data over Wi-Fi")
        streaming_config.streaming_interface = sdk_gen2.StreamingInterface.WIFI_STA
        streaming_config.batch_period_ms = STREAM_BATCH_PERIOD_MS
        streaming_config.advanced_config.endpoint.url = STREAMING_IP
        streaming_config.advanced_config.endpoint.verify_server_certificates = False
    else:
        print("Streaming data over USB")
        streaming_config.streaming_interface = sdk_gen2.StreamingInterface.USB_NCM

    device.set_streaming_config(streaming_config)

    device.start_streaming()
    return device

def image_callback(image_data: ImageData, image_record: ImageDataRecord):
    print(
        f"Received image data of size {image_data.to_numpy_array().shape} with timestamp {image_record.capture_timestamp_ns} ns"
    )

old_time = time.monotonic()
def eyegaze_callback(eyegaze_data: EyeGaze):
    global old_time
    # Only updates every second
    if time.monotonic() - old_time > 1:
        if eyegaze_data.depth != 0:
            print(
                f"Received EyeGaze data at timestamp {eyegaze_data.tracking_timestamp.total_seconds()} sec "
                f"with yaw={eyegaze_data.yaw:.3f} rad, pitch={eyegaze_data.pitch:.3f} rad, "
                f"depth={eyegaze_data.depth:.3f} m"
            )
        else:
            print("Eyegaze not detected")
        old_time = time.monotonic()

def audio_callback(audio_data: AudioData, audio_record: AudioDataRecord, num_channels: int):
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

    source_sample_rate_hz = estimate_sample_rate_hz(audio_record.capture_timestamps_ns)
    chunk_16k = resample_audio(normalized, source_sample_rate_hz)
    if chunk_16k.size > 0:
        chunk_i16 = np.clip(chunk_16k, -1.0, 1.0)
        chunk_i16 = (chunk_i16 * 32767.0).astype(np.int16)
        _data_queue.put(chunk_i16.tobytes())

def setup_streaming_receiver(record_to_vrs: bool) -> receiver.StreamReceiver:
    config = sdk_gen2.HttpServerConfig()
    config.address = "0.0.0.0"
    config.port = 6768

    # Setup the receiver
    stream_receiver = receiver.StreamReceiver()
    stream_receiver.set_server_config(config)
    if record_to_vrs != "":
        stream_receiver.record_to_vrs(record_to_vrs)

    # Register callbacks for each type of data
    # stream_receiver.register_rgb_callback(image_callback)
    stream_receiver.register_audio_callback(audio_callback)
    # stream_receiver.register_eye_gaze_callback(eyegaze_callback)

    return stream_receiver

def get_temp_str(status) -> str:
    temp_str = f"{status.skin_temp_celsius:.1f}°C"
    if status.thermal_mitigation_triggered:
        temp_str += " (throttling)"
    return temp_str

def temperature_monitor_loop(stop_event: threading.Event, device: sdk_gen2.Device) -> None:
    temp_str = None
    while not stop_event.is_set():
        if device is not None:
            try:
                status = device.status()
                if temp_str is None:
                    temp_str = get_temp_str(status)
                    print(f"Initial Temperature: {temp_str}")
                else:
                    temp_str = get_temp_str(status)
                print(f"Temperature: {temp_str}", end="\r")
            except Exception as exc:
                print(f"Temperature read error: {exc}\n")
        stop_event.wait(1.0)
    if temp_str is not None:
        print(f"Final temperature: {temp_str}")

if __name__ == "__main__":
    record_to_vrs = ""

    # Setup device to start streaming
    device = device_streaming()

    if DISPLAY_TEMPERATURE:
        _temp_stop = threading.Event()
        _temp_thread = threading.Thread(target=temperature_monitor_loop, args=(_temp_stop, device), daemon=True)
        _temp_thread.start()
    else:
        init_whisper_model()
        start_transcription_worker()

    # Setup streaming receiver to receive streaming data with callbacks
    stream_receiver = setup_streaming_receiver(record_to_vrs)

    stream_receiver.start_server()

    try:
        # Wait for 10 minutes
        time.sleep(600)
    except KeyboardInterrupt:
        print("Shutting down streaming")

    if DISPLAY_TEMPERATURE:
        _temp_stop.set()

    stop_transcription_worker()

    # Stop streaming
    try:
        device.stop_streaming()
    except RuntimeError:
        print("Failed to stop device streaming")

    # Terminate the server
    stream_receiver.stop_server()