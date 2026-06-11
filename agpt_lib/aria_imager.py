import asyncio

from gum.imagers.imager import Imager

class AriaImager(Imager):
    def __init__(self, request_queue, data_queue):
        super().__init__()
        self.loop = asyncio.get_running_loop()
        self.request_queue = request_queue
        self.data_queue = data_queue
        self.first_image = True

    async def get_image(self):
        # TODO it might be worth looking into observing the quality of this image somehow and
        # requesting another one if it is bad. Everything else takes a while to run so this wouldn't
        # add much time relatively
        await self.request_queue.put(0)
        data = await self.data_queue.get()
        # This is more of a temporary solution to fix the first image being dark that it takes. It
        # seems to work very consistently which implies that the first many images are dark because
        # of adjusting exposure
        if self.first_image:
            self.first_image = False
            for _ in range(20):
                await self.get_image()
            data = await self.get_image()
        return data