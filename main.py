import asyncio
from queue import Queue

from gum import gum
from gum.observers.image_observer import ImageObserver

# For local secret variables
from agpt_lib.agpt_config import *
from agpt_lib.agpt_glasses_handler import AgptGlassesHandler
from agpt_lib.agpt_prompts import *
from agpt_lib.agpt_secrets import *
from agpt_lib.aria_imager import AriaImager
from agpt_lib.transcription_context_generator import TranscriptionContextGenerator
from agpt_lib.transcription_worker import TranscriptionWorker

# TODO Some ideas for future work:
# - There could be a mode of just the image AI that names things that the user is pointing at. This
#   could be as complex as using the hand tracking along with the point cloud to try to get an
#   accurate line to the object they are pointing/looking at

async def main():
    image_request_queue = asyncio.Queue(1)
    image_data_queue = asyncio.Queue(1)
    aria_imager = AriaImager(image_request_queue, image_data_queue)

    audio_data_queue = Queue()
    transcription_worker = TranscriptionWorker(audio_data_queue, WHISPER_MODEL_NAME, TRANSCRIPTION_WARMUP_SEC, PHRASE_TIMEOUT_SEC, False)
    # TODO pipe transcriptions into the prompts. May require a refactor of GUM again to allow many
    # different contexts for initial data
    transcription_worker.start_transcription_worker()

    handler = AgptGlassesHandler(False, image_request_queue, image_data_queue, asyncio.get_running_loop(), audio_data_queue, AUDIO_SAMPLE_RATE, WHISPER_SAMPLE_RATE)
    handler.setup_device(DEVICE_IP, INITIAL_CONNECTION_OVER_WIFI, STREAM_CONFIG_NAME, STREAM_BATCH_PERIOD_MS, STREAMING_IP, STREAM_OVER_WIFI)
    # Setup streaming receiver to receive streaming data with callbacks
    handler.setup_streaming_receiver("", "0.0.0.0", 6768)

    handler.start_device_streaming()
    handler.start_streaming_receiver()

    context_generators = [TranscriptionContextGenerator(transcription_worker)]
    image_observer = ImageObserver("qwen3.5-vision", api_key=LLM_API_TOKEN, api_base=LLM_API_BASE, imager=aria_imager, save_images=True, transcription_prompt=TRANSCRIPTION_PROMPT, summary_prompt=SUMMARY_PROMPT, history_k=4, context_generators=context_generators)

    print("Streaming... Press Ctrl+C to stop")
    try:
        async with gum(
                "Ethan",
                "qwen3.5-vision",
                image_observer,
                api_base=LLM_API_BASE,
                api_key=LLM_API_TOKEN,
                propose_prompt=PROPOSE_PROMPT,
                similar_prompt=SIMILAR_PROMPT,
                revise_prompt=REVISE_PROMPT,
                audit_prompt=AUDIT_PROMPT,
                use_batching=False
            ) as gum_instance:
                try:
                    # await asyncio.sleep(60 * 30)
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    print("\nSleep cancelled by user request.")
                    raise

    except (KeyboardInterrupt, asyncio.CancelledError):
        pass

    print("Shutting down streaming")
    handler.stop_streaming_receiver()
    handler.stop_device_streaming()
    transcription_worker.stop_transcription_worker()
    print("Streaming stopped")

if __name__ == "__main__":
    asyncio.run(main())