import base64

def base64_encode_image(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode()

class Imager:
    def __init__(self):
        pass

    async def get_image(self) -> str:
        """Gets an image in Base64 format str

        Returns:
            str -- Image str in Base64 format
        """
        raise NotImplementedError