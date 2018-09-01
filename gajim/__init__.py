import os

__version__ = "1.0.99"

IS_FLATPAK = False
if os.path.exists('/app/share/run-as-flatpak'):
    IS_FLATPAK = True
