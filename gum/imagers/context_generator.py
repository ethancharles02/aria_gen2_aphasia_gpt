class ContextGenerator:
    """Base class for generating additional context."""

    def __init__(self):
        pass

    async def get_context(self) -> str:
        """Gets additional context as a string.

        Returns:
            str -- Context string that provides extra information
        """
        raise NotImplementedError
