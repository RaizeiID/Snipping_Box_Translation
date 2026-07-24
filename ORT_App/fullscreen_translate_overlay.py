# fullscreen_translate_overlay.py
# F11 Capture All Screen: screenshot -> OCR -> blur original text areas -> draw translated text overlay

import time
import numpy as np
import cv2
import mss

from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QRect, QPoint
from PyQt5.QtGui import QPainter, QPixmap, QImage, QFont, QFontMetrics, QColor, QGuiApplication, QCursor


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _bbox_to_rect(bbox):
    # bbox from easyocr: [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
    xs = [p[0] for p in bbox]
    ys = [p[1] for p in bbox]
    x1, y1 = int(min(xs)), int(min(ys))
    x2, y2 = int(max(xs)), int(max(ys))
    return x1, y1, max(1, x2 - x1), max(1, y2 - y1)


class FullScreenCaptureWorker(QThread):
    finished_frame = pyqtSignal(object)  # QPixmap
    debug = pyqtSignal(str)

    def __init__(self, get_reader_fn, translate_fn, log_fn, conf_min=0.35):
        super().__init__()
        self.get_reader_fn = get_reader_fn
        self.translate_fn = translate_fn
        self.log_fn = log_fn
        self.conf_min = conf_min

        self._pending = False
        self._running = True

    def request_capture(self):
        self._pending = True

    def stop(self):
        self._running = False
        self._pending = False
        self.quit()
        self.wait()

    def run(self):
        # Worker idle until requested
        while self._running:
            if not self._pending:
                self.msleep(50)
                continue

            self._pending = False
            try:
                self.debug.emit("[F11] Capturing full screen...")

                with mss.mss() as sct:
                    mon = sct.monitors[0]  # all monitors
                    raw = np.array(sct.grab(mon))  # BGRA
                    frame_bgr = raw[:, :, :3]
                    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

                reader = self.get_reader_fn()
                if reader is None:
                    self.debug.emit("[F11] OCR Reader not ready.")
                    continue

                t0 = time.time()
                # detail=1 => bbox + text + conf
                results = reader.readtext(frame_rgb, detail=1, paragraph=False)
                dt_ocr = (time.time() - t0) * 1000.0
                self.debug.emit(f"[F11] OCR results={len(results)} | {dt_ocr:.0f}ms")

                # Prepare a "clean" base by blurring text regions
                clean_rgb = frame_rgb.copy()

                items = []
                for r in results:
                    if not r or len(r) < 2:
                        continue
                    bbox, text = r[0], r[1]
                    conf = r[2] if len(r) >= 3 else 1.0
                    if conf < self.conf_min:
                        continue
                    text = (text or "").strip()
                    if len(text) < 2:
                        continue

                    x, y, w, h = _bbox_to_rect(bbox)

                    # pad a little
                    pad = max(2, int(min(w, h) * 0.08))
                    x2 = x - pad
                    y2 = y - pad
                    w2 = w + pad * 2
                    h2 = h + pad * 2

                    x2 = _clamp(x2, 0, clean_rgb.shape[1] - 1)
                    y2 = _clamp(y2, 0, clean_rgb.shape[0] - 1)
                    w2 = _clamp(w2, 1, clean_rgb.shape[1] - x2)
                    h2 = _clamp(h2, 1, clean_rgb.shape[0] - y2)

                    roi = clean_rgb[y2:y2 + h2, x2:x2 + w2]
                    if roi.size == 0:
                        continue

                    # Blur original text region to "erase" it visually
                    # (Looks like Google translate screenshot overlay style)
                    k = max(7, (min(w2, h2) // 2) | 1)  # odd kernel
                    blur = cv2.GaussianBlur(roi, (k, k), 0)
                    clean_rgb[y2:y2 + h2, x2:x2 + w2] = blur

                    items.append((x2, y2, w2, h2, text))

                # Convert to QImage for drawing
                h_img, w_img = clean_rgb.shape[:2]
                qimg = QImage(clean_rgb.data, w_img, h_img, w_img * 3, QImage.Format_RGB888).copy()

                painter = QPainter(qimg)
                painter.setRenderHint(QPainter.Antialiasing, True)
                painter.setRenderHint(QPainter.TextAntialiasing, True)

                # Draw translated text in the same rectangles
                t1 = time.time()
                for (x, y, w, h, src_text) in items:
                    try:
                        out = self.translate_fn(src_text)
                    except Exception:
                        out = src_text
                    out = (out or "").strip()
                    if not out:
                        continue

                    rect = QRect(x, y, w, h)

                    # Fit font size into rect
                    font_size = max(10, int(h * 0.70))
                    font = QFont("Segoe UI", font_size)
                    fm = QFontMetrics(font)

                    # shrink until fits height
                    for _ in range(12):
                        br = fm.boundingRect(rect, Qt.TextWordWrap, out)
                        if br.height() <= rect.height() and br.width() <= rect.width():
                            break
                        font_size -= 1
                        if font_size < 9:
                            break
                        font = QFont("Segoe UI", font_size)
                        fm = QFontMetrics(font)

                    painter.setFont(font)

                    # Shadow (black) then main (white)
                    shadow_rect = QRect(rect.x() + 1, rect.y() + 1, rect.width(), rect.height())
                    painter.setPen(QColor(0, 0, 0, 220))
                    painter.drawText(shadow_rect, Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignVCenter, out)

                    painter.setPen(QColor(255, 255, 255, 255))
                    painter.drawText(rect, Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignVCenter, out)

                painter.end()
                dt_draw = (time.time() - t1) * 1000.0
                self.debug.emit(f"[F11] Render done | {dt_draw:.0f}ms | boxes={len(items)}")

                pix = QPixmap.fromImage(qimg)
                self.finished_frame.emit(pix)

            except Exception as e:
                self.debug.emit(f"[F11] ERR: {e}")


class FullScreenTranslateOverlay(QWidget):
    """
    Transparent click-through overlay that displays a translated screenshot.
    F11: recapture (handled externally).
    """
    def __init__(self, get_reader_fn, translate_fn, log_fn):
        super().__init__()
        self.get_reader_fn = get_reader_fn
        self.translate_fn = translate_fn
        self.log_fn = log_fn

        self._pix = None

        # Fullscreen overlay window (click-through)
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        try:
            self.setWindowFlag(Qt.WindowTransparentForInput, True)
        except Exception:
            pass

        # Match all monitors geometry (best effort)
        app = QApplication.instance()
        if app:
            scr = None
            try:
                scr = QGuiApplication.screenAt(QCursor.pos())
            except Exception:
                scr = None
            if scr is None:
                scr = app.primaryScreen()
            if scr:
                geo = scr.geometry()
            # If multi-monitor, mss.monitors[0] may be larger; we still show fullscreen on primary.
            # It's okay; overlay acts as "visual translate screen" mainly on primary.
            self.setGeometry(geo)

        self.worker = FullScreenCaptureWorker(get_reader_fn, translate_fn, log_fn)
        self.worker.finished_frame.connect(self._on_frame)
        self.worker.debug.connect(self._on_debug)
        self.worker.start()

    def _on_debug(self, msg: str):
        try:
            self.log_fn(msg)
        except Exception:
            print(msg, flush=True)

    def _on_frame(self, pix: QPixmap):
        self._pix = pix
        # Resize overlay to pix size if needed
        if pix and not pix.isNull():
            self.setFixedSize(pix.size())
        self.update()

    def request_recapture(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self.worker.request_capture()

    def close_overlay(self):
        try:
            self.worker.stop()
        except Exception:
            pass
        self.close()

    def paintEvent(self, event):
        if not self._pix:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        p.drawPixmap(QPoint(0, 0), self._pix)
        p.end()

    def closeEvent(self, event):
        try:
            self.worker.stop()
        except Exception:
            pass
        event.accept()
