import asyncio
import sys
import os
from openai import AsyncOpenAI
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from gum.observers.image_observer import ImageObserver
from gum.imagers.imager import Imager, base64_encode_image
from gum import gum
from gum.schemas import PropositionSchema, get_schema

class TestImager(Imager):
    def __init__(self):
        super().__init__()
        self.i = 0
        self.before_path = ""
        self.after_path = ""

    async def get_image(self):
        img_path = self.before_path if self.i % 2 == 0 else self.after_path
        encoded = base64_encode_image(img_path)
        self.i += 1
        return encoded

def test_image_observer():
    import asyncio

    test_imager = TestImager()

    async def test():
        observer = ImageObserver("qwen3.5-vision", api_key="EMPTY", api_base="http://localhost:11434/v1", imager=test_imager)
        update = await observer.update_queue.get()
        print(f"\n=== UPDATE RECEIVED ===\n{update.content}\n")
        observer._running = False
        await asyncio.sleep(0.5)  # Allow worker to finish

    asyncio.run(test())

async def test_gum():
    gum_instance = gum("Ethan", model="qwen3.5-text")
    await gum_instance.connect_db()
    propositions = await gum_instance.query("")
    print(propositions[0][0].reasoning)

PROMPT = """"""

async def test_text_model():
    api_base="http://localhost:11434/v1"
    api_key="EMPTY"
    client = AsyncOpenAI(
        base_url=api_base,
        api_key=api_key
    )
    schema = PropositionSchema.model_json_schema()
    rsp = await client.chat.completions.create(
        model="qwen3.5-text",
        messages=[{"role": "user", "content": PROMPT}],
        response_format=get_schema(schema),
    )
    print(f"{rsp.choices[0].message.content}\n\n")

if __name__ == "__main__":
    asyncio.run(test_gum())
    # asyncio.run(test_text_model())
    # test_image_observer()