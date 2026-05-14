from string import Formatter
import base64

def base64_encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode()

class VisionModel:
    def __init__(self):
        self.instructions: str = ""
        self.required_instructions_keys: set = set()

    def setup(self):
        raise NotImplementedError

    def set_instructions(self, instructions: str):
        self.instructions = instructions
        self.required_instructions_keys = {field_name for _, field_name, _, _ in Formatter().parse(instructions) if field_name is not None}

    def _generate_response(self, prompt: str, base64_img: bytes) -> str:
        raise NotImplementedError

    def generate_response(self, replace_dict: dict, base64_img: bytes) -> str:
        for required_key in self.required_instructions_keys:
            if required_key not in replace_dict:
                raise KeyError(f"Couldn't find required key in replace dictionary: {required_key}")
        return self._generate_response(self.instructions.format(**replace_dict), base64_img)