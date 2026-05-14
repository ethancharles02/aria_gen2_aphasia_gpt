from openai import OpenAI
from pathlib import Path

from .vision_model import VisionModel, base64_encode_image

class Qwen35_9b(VisionModel):
    def __init__(self):
        super().__init__()

        self.client = None

    def setup(self):
        self.client = OpenAI(base_url="http://localhost:11434/v1", api_key="EMPTY")

    def _generate_response(self, prompt, base64_img):
        if self.client is None:
            print(f"{self.__class__.__str__}WARNING: Attempted to generate a response without calling setup first")

        # Handle both single image (string) and multiple images (list)
        images = base64_img if isinstance(base64_img, list) else [base64_img]
        # num_images = len(images)

        # Join images with a delimiter
        # concatenated_images = "".join(images)
        content = [
            *[{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image}"}} for image in images],
            {
                "type": "text",
                "text": prompt
            }
        ]

        messages = [
            {
                "role": "user",
                "content": content
            }
        ]
        chat_response = self.client.chat.completions.create(
            model="qwen3.5-vision",
            messages=messages,
            max_tokens=81920,
            temperature=1,
            top_p=0.95,
            presence_penalty=1.5,
            extra_body={
                "top_k": 20,
                "chat_template_kwargs": {"enable_thinking": False},
            },
        )
        answer = chat_response.choices[0].message.content
        # TODO This isn't a valid production setup. Handle it better
        if not answer:
            raise RuntimeError("Something went wrong with the model and it didn't produce a message")
        return answer


def test_qwen35_9b():
    """Test function to run the Qwen35_9b model and print a response."""
    model = Qwen35_9b()
    model.setup()
    model.set_instructions("What is in this image?")

    project_root = Path(__file__).resolve().parents[2]
    image_path = project_root / "testing" / "mathv-1327.jpg"
    base64_image = base64_encode_image(image_path)

    response = model.generate_response({}, base64_image)

    print(response)