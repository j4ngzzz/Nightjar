"""nightjarzzz has been renamed to nightjar-verify.

Install the new package:
    pip uninstall nightjarzzz
    pip install nightjar-verify
"""
import warnings
warnings.warn(
    "nightjarzzz has been renamed to nightjar-verify. "
    "Please run: pip uninstall nightjarzzz && pip install nightjar-verify",
    DeprecationWarning,
    stacklevel=2,
)
