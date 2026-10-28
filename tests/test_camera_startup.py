"""Exercise blocked camera drivers without opening physical hardware."""
import threading

import numpy as np

from app.camera import CameraCapture


def test_start_and_cancel_do_not_wait_for_driver(monkeypatch):
    opening = threading.Event()
    unblock = threading.Event()
    released_by = []

    class SlowDevice:
        def __init__(self, *args):
            opening.set()
            assert unblock.wait(3)

        def release(self):
            released_by.append(threading.get_ident())

    monkeypatch.setattr("app.camera.cv2.VideoCapture", SlowDevice)
    camera = CameraCapture()
    caller = threading.get_ident()
    try:
        assert camera.start()
        assert opening.wait(1)  # The caller reaches here while the driver is still blocked.
        camera.stop(wait=False)
        assert camera.is_alive()
        assert not camera.start()  # No second owner while open() is outstanding.
        assert not released_by
    finally:
        unblock.set()
        camera.stop()
    assert not camera.is_alive()
    assert released_by and released_by[0] != caller


def test_failed_device_is_reported_without_silent_mock_fallback(monkeypatch):
    released = []

    class UnavailableDevice:
        def __init__(self, *args):
            pass

        def isOpened(self):
            return False

        def release(self):
            released.append(True)

    monkeypatch.setattr("app.camera.cv2.VideoCapture", UnavailableDevice)
    camera = CameraCapture()
    camera.start()
    camera.thread.join(timeout=2)
    assert not camera.is_alive()
    assert camera.startup_error
    assert not camera.is_mock
    assert not camera.read()[0]
    assert released == [True]


def test_restart_discards_frame_from_previous_session(monkeypatch):
    camera = CameraCapture(is_mock=True)
    with camera._lock:
        camera.latest_frame = np.ones((2, 2, 3), dtype=np.uint8)
        camera.latest_timestamp = 1.0
    entered = threading.Event()
    unblock = threading.Event()

    def slow_mock():
        entered.set()
        assert unblock.wait(3)
        return np.zeros((2, 2, 3), dtype=np.uint8)

    monkeypatch.setattr(camera, "_generate_mock_frame", slow_mock)
    try:
        camera.start()
        assert entered.wait(1)
        assert camera.read() == (False, None, 0.0)
    finally:
        unblock.set()
        camera.stop()


def test_measured_fps_uses_delivered_frames_not_requested_or_driver_rate(monkeypatch):
    camera = CameraCapture(fps=60)
    camera.reported_fps = 60.0
    # A driver may report 60 even when the sensor delivers only 30 distinct reads.
    camera._frame_times.extend(10.0 + i / 30 for i in range(30))
    monkeypatch.setattr("app.camera.time.perf_counter", lambda: 10.0 + 29 / 30)
    assert abs(camera.measured_fps() - 30.0) < 0.01
    monkeypatch.setattr("app.camera.time.perf_counter", lambda: 12.0)
    assert camera.measured_fps() == 0.0  # Frozen/stopped capture must not keep showing 60.


def test_read_ignores_already_consumed_frame_and_preserves_safe_copy_default():
    camera = CameraCapture()
    camera.latest_frame = np.ones((2, 2, 3), dtype=np.uint8)
    camera.latest_timestamp = 1.0
    assert camera.read(after_timestamp=1.0) == (False, None, 0.0)
    _, copy, _ = camera.read()
    copy[:] = 0
    assert np.all(camera.latest_frame == 1)
    _, shared, _ = camera.read(copy=False)
    assert shared is camera.latest_frame
