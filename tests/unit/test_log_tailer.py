"""Tests for log tailer."""

import tempfile
from pathlib import Path

import pytest

from titrack.parser.log_tailer import LogTailer


@pytest.fixture
def temp_log():
    """Create a temporary log file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        f.write("Line 1\n")
        f.write("Line 2\n")
        f.write("Line 3\n")
        temp_path = Path(f.name)
    yield temp_path
    temp_path.unlink()


class TestLogTailer:
    """Tests for LogTailer."""

    def test_read_all_lines(self, temp_log):
        tailer = LogTailer(temp_log)
        lines = list(tailer.read_all_lines())
        assert lines == ["Line 1", "Line 2", "Line 3"]

    def test_read_new_lines_from_position(self, temp_log):
        tailer = LogTailer(temp_log)

        # Read initial content
        list(tailer.read_new_lines())

        # Add more content
        with open(temp_log, "a") as f:
            f.write("Line 4\n")
            f.write("Line 5\n")

        # Should only get new lines
        new_lines = list(tailer.read_new_lines())
        assert new_lines == ["Line 4", "Line 5"]

    def test_handles_partial_line(self, temp_log):
        tailer = LogTailer(temp_log)
        list(tailer.read_new_lines())

        # Write partial line (no newline)
        with open(temp_log, "a") as f:
            f.write("Partial")

        # Should not return partial line yet
        lines = list(tailer.read_new_lines())
        assert lines == []

        # Complete the line
        with open(temp_log, "a") as f:
            f.write(" line\n")

        # Now should return the complete line
        lines = list(tailer.read_new_lines())
        assert lines == ["Partial line"]

    def test_position_tracking(self, temp_log):
        tailer = LogTailer(temp_log)
        list(tailer.read_new_lines())

        assert tailer.position > 0
        assert tailer.file_size > 0

    def test_set_position_for_resume(self, temp_log):
        tailer1 = LogTailer(temp_log)
        list(tailer1.read_new_lines())
        saved_pos = tailer1.position
        saved_size = tailer1.file_size

        # Simulate resume with new tailer
        tailer2 = LogTailer(temp_log)
        tailer2.set_position(saved_pos, saved_size)

        # Add new content
        with open(temp_log, "a") as f:
            f.write("New line\n")

        # Should only get the new line
        lines = list(tailer2.read_new_lines())
        assert lines == ["New line"]

    def test_detects_log_rotation(self, temp_log):
        tailer = LogTailer(temp_log)
        list(tailer.read_new_lines())

        # Simulate rotation - file shrinks
        with open(temp_log, "w") as f:
            f.write("New log\n")

        # Should reset and read from beginning
        lines = list(tailer.read_new_lines())
        assert lines == ["New log"]

    def test_reset(self, temp_log):
        tailer = LogTailer(temp_log)
        list(tailer.read_new_lines())

        tailer.reset()

        # Should read from beginning again
        lines = list(tailer.read_new_lines())
        assert lines == ["Line 1", "Line 2", "Line 3"]

    def test_nonexistent_file(self):
        tailer = LogTailer(Path("/nonexistent/path.log"))
        lines = list(tailer.read_new_lines())
        assert lines == []

    def test_set_position_rotation_detected(self, temp_log):
        tailer = LogTailer(temp_log)

        # Simulate saved position larger than current file
        tailer.set_position(99999, 100000)

        # Position should be reset to 0
        lines = list(tailer.read_new_lines())
        assert "Line 1" in lines  # Read from beginning
