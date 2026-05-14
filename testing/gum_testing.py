import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from gum.models.vision_qwen35_9b import test_qwen35_9b
from gum.observers.image_observer import test_image_observer
from gum import gum

if __name__ == "__main__":
    # test_qwen35_9b()
    test_image_observer()