"""
Observer module for GUM - General User Models.

This module provides observer classes for different types of user interactions.
"""

from .observer import Observer
# from .screen import Screen
from .image_observer import ImageObserver

__all__ = ["Observer", "ImageObserver"]