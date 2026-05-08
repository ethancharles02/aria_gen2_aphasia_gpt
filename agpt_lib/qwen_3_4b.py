from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
import time
import warnings

from aphasia_llm import AphasiaLLM

model_name = "Qwen/Qwen3-4B"

class Qwen3_4bLLM(AphasiaLLM):
    def __init__(self):
        super().__init__()
        self.tokenizer = None
        self.device = None
        self.model = None

    def setup(self):
        def get_device_and_dtype() -> tuple[torch.device, torch.dtype]:
            if torch.cuda.is_available():
                device = torch.device("cuda")
                print(f"Using GPU: {torch.cuda.get_device_name(device)}")
                return device, torch.float16

            warnings.warn(
                "No GPU detected by PyTorch. Falling back to CPU; generation may be much slower.",
                stacklevel=2,
            )
            return torch.device("cpu"), torch.float32

        self.device, dtype = get_device_and_dtype()

        # load the tokenizer and the model
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            dtype=dtype,
            device_map=None
        )
        self.model.to(self.device)
        self.model.eval()
        print(f"Model first parameter device: {next(self.model.parameters()).device}")

    def _generate_response(self, prompt: str) -> str:
        if self.device is None or self.tokenizer is None or self.model is None:
            raise RuntimeError("No device or tokenizer found. Did you run setup()?")

        messages = [
            {"role": "user", "content": prompt}
        ]
        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False
        )
        model_inputs = self.tokenizer([text], return_tensors="pt").to(self.device)

        old_time = time.monotonic()
        # conduct text completion
        generated_ids = self.model.generate(
            **model_inputs,
            max_new_tokens=32768
        )
        print(f"Time to completion (seconds): {time.monotonic() - old_time}")

        output_ids = generated_ids[0][len(model_inputs.input_ids[0]):].tolist()

        # parsing thinking content
        try:
            # rindex finding 151668 (</think>)
            index = len(output_ids) - output_ids[::-1].index(151668)
        except ValueError:
            index = 0

        # thinking_content = self.tokenizer.decode(output_ids[:index], skip_special_tokens=True).strip("\n")
        content = self.tokenizer.decode(output_ids[index:], skip_special_tokens=True).strip("\n")

        # print("thinking content:", thinking_content)
        # print("content:", content)
        return content

if __name__ == "__main__":
    from aphasia_config import APHASIA_INSTRUCTION_PROMPT
    model = Qwen3_4bLLM()
    model.setup()
    model.set_instructions(APHASIA_INSTRUCTION_PROMPT)
    replace_dict = {
        "name": "Ethan",
        "age": "23",
        "about": "I enjoy programming",
        "setting": "workplace",
        "tone": "casual",
        "conversationType": "chat",
        "utterance": "uh python uh good simple"
    }
    print(model.generate_response(replace_dict))