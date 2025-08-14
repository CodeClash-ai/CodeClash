__version__ = "0.0.0"

# Optional viewer import - only if Flask dependencies are available
try:
    from . import viewer

    __all__ = ["viewer"]
except ImportError:
    __all__ = []
