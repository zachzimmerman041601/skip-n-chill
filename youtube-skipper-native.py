"""
Skip n' Chill - YouTube Ad Skipper
Runs in background and clicks the skip button using real mouse input.

Install: pip install -r requirements.txt
Run: python youtube-skipper-native.py

Setup:
1. Go to YouTube and wait for an ad with a skip button
2. Screenshot JUST the skip button (crop tightly)
3. Save as 'skip_button.png' in the same folder as this script

Note: On macOS, grant accessibility permissions when prompted.
"""

import pyautogui
import time
import sys
import os
import threading
import ctypes
from PIL import ImageGrab
import cv2
import numpy as np
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QFont

pyautogui.PAUSE = 0.1
pyautogui.FAILSAFE = True


def get_resource_path(filename):
    """Get path to resource, works for dev and PyInstaller."""
    if getattr(sys, '_MEIPASS', None):
        return os.path.join(sys._MEIPASS, filename)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)


import platform

# Use platform-specific skip button image
if platform.system() == 'Windows':
    SKIP_BUTTON_IMAGE = get_resource_path('skip_button_windows.png')
else:
    SKIP_BUTTON_IMAGE = get_resource_path('skip_button.png')


def get_display_scaling():
    """Detect display scaling factor (Retina/HiDPI support)."""
    screenshot = ImageGrab.grab()
    screenshot_width = screenshot.size[0]
    screen_width = pyautogui.size()[0]
    scale = screenshot_width / screen_width
    return scale


def is_youtube_active():
    """Check if YouTube is in the active window title."""
    try:
        if platform.system() == 'Windows':
            # Get active window handle and title
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
            window_title = buf.value.lower()
            return 'youtube' in window_title
        else:
            # macOS/Linux - just return True for now (can be improved)
            return True
    except Exception:
        return False


def find_skip_button(scale):
    """Locate the skip button using edge detection + template matching.

    Uses Canny edge detection for more robust matching across different
    color schemes and brightness levels. Only searches bottom-right quadrant
    where YouTube skip buttons appear.
    """
    try:
        screenshot = ImageGrab.grab()
        screenshot_np = np.array(screenshot)

        # Only search bottom-right quadrant of screen (where skip button appears)
        h, w = screenshot_np.shape[:2]
        # Skip button is typically in bottom-right area of video
        search_region = screenshot_np[h//2:, w//2:]
        region_offset_x = w // 2
        region_offset_y = h // 2

        # Convert to grayscale
        search_gray = cv2.cvtColor(search_region, cv2.COLOR_RGB2GRAY)

        # Apply edge detection for more robust matching
        search_edges = cv2.Canny(search_gray, 50, 150)

        template = cv2.imread(SKIP_BUTTON_IMAGE, cv2.IMREAD_GRAYSCALE)
        if template is None:
            return None

        template_edges = cv2.Canny(template, 50, 150)

        # Try multiple scales
        best_match = None
        best_confidence = 0
        scales_to_try = [1.0, 0.9, 1.1, 0.8, 1.2, 0.7, 1.3]

        for template_scale in scales_to_try:
            if template_scale != 1.0:
                new_w = int(template_edges.shape[1] * template_scale)
                new_h = int(template_edges.shape[0] * template_scale)
                if new_w < 10 or new_h < 10:
                    continue
                scaled_template = cv2.resize(template_edges, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            else:
                scaled_template = template_edges

            # Skip if template is larger than search region
            if scaled_template.shape[0] > search_edges.shape[0] or scaled_template.shape[1] > search_edges.shape[1]:
                continue

            # Use TM_CCORR_NORMED for edge matching (works better with edges)
            result = cv2.matchTemplate(search_edges, scaled_template, cv2.TM_CCORR_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            if max_val > best_confidence:
                best_confidence = max_val
                th, tw = scaled_template.shape
                # Calculate center position in full screenshot coordinates
                center_x = region_offset_x + max_loc[0] + tw // 2
                center_y = region_offset_y + max_loc[1] + th // 2
                best_match = (center_x, center_y, max_val, template_scale)

        # Edge matching threshold (0.55 for better accuracy)
        if best_match and best_confidence >= 0.55:
            center_x, center_y, confidence, matched_scale = best_match
            screen_x = int(center_x / scale)
            screen_y = int(center_y / scale)
            return (screen_x, screen_y, confidence)

        # Return debug info
        if best_match:
            return (0, 0, -best_confidence)

    except Exception as e:
        print(f"Error in find_skip_button: {e}")

    return None


def click_at(x, y):
    """Perform a real mouse click at coordinates."""
    pyautogui.click(x, y)


class SignalEmitter(QObject):
    """Helper class to emit signals from worker thread."""
    update_status = Signal(str, int)
    stop_requested = Signal()


class YouTubeAdSkipper(QMainWindow):
    def __init__(self):
        super().__init__()
        self.running = False
        self.thread = None
        self.scale = None
        self.clicks_count = 0
        self.signals = SignalEmitter()

        self.signals.update_status.connect(self._on_status_update)
        self.signals.stop_requested.connect(self._stop)

        self.image_found = os.path.exists(SKIP_BUTTON_IMAGE)

        self._setup_ui()
        self._center_window()

    def _setup_ui(self):
        self.setWindowTitle("Skip n' Chill")
        self.setFixedSize(300, 220)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # Title
        title = QLabel("Skip n' Chill")
        title.setFont(QFont("Helvetica", 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        layout.addSpacing(10)

        # Status row
        status_layout = QHBoxLayout()
        status_layout.setAlignment(Qt.AlignCenter)

        status_text = QLabel("Status:")
        status_layout.addWidget(status_text)

        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: gray; font-size: 16px;")
        status_layout.addWidget(self.status_dot)

        self.status_label = QLabel("Stopped")
        self.status_label.setStyleSheet("color: gray;")
        status_layout.addWidget(self.status_label)

        layout.addLayout(status_layout)

        # Info label
        self.info_label = QLabel("")
        self.info_label.setStyleSheet("color: gray; font-size: 12px;")
        self.info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.info_label)

        # Counter
        self.counter_label = QLabel("Ads skipped: 0")
        self.counter_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.counter_label)

        layout.addSpacing(5)

        # Toggle button
        self.toggle_btn = QPushButton("Start")
        self.toggle_btn.setFixedHeight(35)
        self.toggle_btn.clicked.connect(self._toggle)
        layout.addWidget(self.toggle_btn)

        # Warning if image not found
        if not self.image_found:
            self.toggle_btn.setEnabled(False)
            warning = QLabel("skip_button.png not found!\nSee setup instructions.")
            warning.setStyleSheet("color: red;")
            warning.setAlignment(Qt.AlignCenter)
            layout.addWidget(warning)

        # Help text
        help_label = QLabel("Move mouse to top-left corner to emergency stop")
        help_label.setStyleSheet("color: gray; font-size: 10px;")
        help_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(help_label)

        layout.addStretch()

    def _center_window(self):
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def _toggle(self):
        if self.running:
            self._stop()
        else:
            self._start()

    def _start(self):
        self.running = True
        self.toggle_btn.setText("Stop")
        self.status_label.setText("Running")
        self.status_label.setStyleSheet("color: #22c55e;")
        self.status_dot.setStyleSheet("color: #22c55e; font-size: 16px;")

        if self.scale is None:
            self.scale = get_display_scaling()

        self.thread = threading.Thread(target=self._skipper_loop, daemon=True)
        self.thread.start()

    def _stop(self):
        self.running = False
        self.toggle_btn.setText("Start")
        self.status_label.setText("Stopped")
        self.status_label.setStyleSheet("color: gray;")
        self.status_dot.setStyleSheet("color: gray; font-size: 16px;")
        self.info_label.setText("")

    def _skipper_loop(self):
        while self.running:
            try:
                # Only scan when YouTube is the active window
                if not is_youtube_active():
                    self.signals.update_status.emit("Waiting for YouTube...", self.clicks_count)
                    time.sleep(1)
                    continue

                result = find_skip_button(self.scale)

                if result:
                    x, y, confidence = result
                    if confidence > 0:  # Positive = good match, click it
                        click_at(x, y)
                        self.clicks_count += 1
                        self.signals.update_status.emit(f"Clicked! ({confidence:.0%} match)", self.clicks_count)
                        time.sleep(2)
                    else:  # Negative = debug info, show best confidence but don't click
                        self.signals.update_status.emit(f"Scanning... (best: {-confidence:.0%})", self.clicks_count)
                        time.sleep(0.5)
                else:
                    self.signals.update_status.emit("Scanning...", self.clicks_count)
                    time.sleep(0.5)

            except pyautogui.FailSafeException:
                self.signals.update_status.emit("Failsafe triggered", self.clicks_count)
                self.signals.stop_requested.emit()
                break
            except Exception as e:
                print(f"Error in skipper loop: {e}")
                time.sleep(0.5)

    def _on_status_update(self, status, count):
        self.info_label.setText(status)
        self.counter_label.setText(f"Ads skipped: {count}")

    def closeEvent(self, event):
        self.running = False
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = YouTubeAdSkipper()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
