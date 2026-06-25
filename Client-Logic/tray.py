"""
tray.py — System Tray Indicator for ShadowDrive
Shows sync status icon in the macOS menu bar with basic controls.
"""

import threading
import os
import sys
from PIL import Image, ImageDraw
from loguru import logger

try:
    import pystray
    from pystray import MenuItem as item
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False
    logger.warning("pystray not installed. System tray disabled.")

import config


class TrayIcon:
    """System tray icon manager."""

    ICON_SIZE = 22  # macOS menu bar icon size

    def __init__(self):
        self._icon = None
        self._status = "idle"  # idle, syncing, error, offline

    def _create_icon_image(self, color: str = "#10b981") -> Image.Image:
        """Generate a simple colored circle icon."""
        img = Image.new("RGBA", (self.ICON_SIZE, self.ICON_SIZE), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        margin = 2
        draw.ellipse(
            [margin, margin, self.ICON_SIZE - margin, self.ICON_SIZE - margin],
            fill=color,
        )
        return img

    def _get_color_for_status(self) -> str:
        """Map status to icon color."""
        return {
            "idle": "#10b981",    # Green — synced
            "syncing": "#3b82f6", # Blue — active
            "error": "#ef4444",   # Red — error
            "offline": "#6b7280", # Gray — offline
        }.get(self._status, "#10b981")

    def update_status(self, status: str):
        """Update tray icon color based on sync status."""
        self._status = status
        if self._icon:
            self._icon.icon = self._create_icon_image(self._get_color_for_status())

    def _on_open_folder(self, icon, item):
        """Open the sync folder in Finder."""
        os.system(f'open "{config.WATCH_DIR}"')

    def _on_open_ui(self, icon, item):
        """Open the web UI in default browser."""
        os.system('open "http://127.0.0.1:5173"')

    def _on_quit(self, icon, item):
        """Quit the application."""
        icon.stop()
        sys.exit(0)

    def start(self):
        """Start the tray icon in a background thread."""
        if not TRAY_AVAILABLE:
            return

        menu = pystray.Menu(
            item("ShadowDrive", None, enabled=False),
            pystray.Menu.SEPARATOR,
            item("Open Sync Folder", self._on_open_folder),
            item("Open Dashboard", self._on_open_ui),
            pystray.Menu.SEPARATOR,
            item("Quit", self._on_quit),
        )

        self._icon = pystray.Icon(
            "shadowdrive",
            icon=self._create_icon_image(),
            title="ShadowDrive — Synced",
            menu=menu,
        )

        thread = threading.Thread(target=self._icon.run, daemon=True)
        thread.start()
        logger.info("System tray icon started.")


# Module-level singleton
tray = TrayIcon()
