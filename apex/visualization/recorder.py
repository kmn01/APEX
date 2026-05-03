"""Small MP4 recorder abstraction for pygame-rendered RGB frames."""

from __future__ import annotations

from pathlib import Path

import numpy as np

try:
    import imageio.v2 as imageio
except ImportError:  # pragma: no cover - optional dependency guard
    imageio = None


class VideoRecorder:
    """Write RGB frames to MP4 using imageio/ffmpeg."""

    def __init__(self, output_path: str | Path, fps: int = 30) -> None:
        if imageio is None:
            msg = "imageio is required for video recording. Install with: pip install -e '.[viz]'"
            raise ImportError(msg)
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._writer = imageio.get_writer(str(self.output_path), fps=max(1, int(fps)))
        self._closed = False

    def write_frame(self, rgb_frame: np.ndarray) -> None:
        """Append one RGB frame shaped as (height, width, 3)."""
        if rgb_frame.ndim != 3 or rgb_frame.shape[2] != 3:
            raise ValueError("Expected RGB frame with shape (H, W, 3)")
        self._writer.append_data(rgb_frame)

    def close(self) -> None:
        """Finalize the encoded file."""
        if self._closed or self._writer is None:
            return
        self._closed = True
        w = self._writer
        self._writer = None
        w.close()
