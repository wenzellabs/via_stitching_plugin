"""Via stitching plugin package

This package registers the ActionPlugin with pcbnew when imported by KiCad.
"""
from .via_stitching_action import ViaStitchingPlugin

try:
    # Register the plugin with pcbnew when this package is imported by KiCad.
    ViaStitchingPlugin().register()
except Exception as e:
    # When not running inside KiCad (e.g., during static analysis), print a message
    # but don't raise so importing the package outside KiCad is safe.
    print("via_stitching_plugin: plugin registration skipped:", e)
