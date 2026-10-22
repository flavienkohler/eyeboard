"""EyeBoard package."""

from importlib.metadata import PackageNotFoundError, version

__all__ = ["__version__"]

try:
    __version__ = version("eyeboard")
except PackageNotFoundError:  # running from a source folder that was never installed
    __version__ = "0+unknown"
