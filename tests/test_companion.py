"""Tests for the Textual companion app."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from tui_input.companion import MIN_HEIGHT, CompanionApp, InputArea

_IME_DELAY = 0.2  # Wait for IME commit delay (50ms) + margin for CI


@pytest.fixture
def mock_tmux() -> MagicMock:
    """Mock all tmux operations to avoid requiring tmux in tests."""
    with (
        patch("tui_input.companion.pane_pid", return_value=None),
        patch("tui_input.companion.pane_alive", return_value=True),
        patch("tui_input.companion.submit_to_pane") as mock_submit,
        patch("tui_input.companion.send_raw") as mock_raw,
        patch("tui_input.companion.send_keys") as mock_keys,
        patch("tui_input.companion.resize_pane") as mock_resize,
        patch("tui_input.companion.pane_height", return_value=MIN_HEIGHT),
        patch("tui_input.companion.cancel_copy_mode"),
        patch("tui_input.companion.unset_hook"),
    ):
        yield MagicMock(
            submit_to_pane=mock_submit,
            send_raw=mock_raw,
            send_keys=mock_keys,
            resize_pane=mock_resize,
        )


class TestCompanionApp:
    @pytest.fixture
    def app(self, mock_tmux: MagicMock) -> CompanionApp:
        return CompanionApp(target_pane="%0")

    async def test_app_starts_with_empty_editor(self, app: CompanionApp) -> None:
        async with app.run_test():
            editor = app.query_one("#editor", InputArea)
            assert editor.text == ""

    async def test_enter_sends_text(self, app: CompanionApp, mock_tmux: MagicMock) -> None:
        async with app.run_test() as pilot:
            editor = app.query_one("#editor", InputArea)
            editor.text = "hello world"
            await pilot.press("enter")
            await asyncio.sleep(_IME_DELAY)
            mock_tmux.submit_to_pane.assert_called_once_with("%0", "hello world")
            assert editor.text == ""

    async def test_enter_empty_forwards_to_agent(
        self, app: CompanionApp, mock_tmux: MagicMock
    ) -> None:
        async with app.run_test() as pilot:
            await pilot.press("enter")
            await asyncio.sleep(_IME_DELAY)
            mock_tmux.submit_to_pane.assert_not_called()
            # Empty Enter should forward \r to agent
            mock_tmux.send_raw.assert_called_once_with("%0", "\r")

    async def test_escape_clears_input(self, app: CompanionApp, mock_tmux: MagicMock) -> None:
        async with app.run_test() as pilot:
            editor = app.query_one("#editor", InputArea)
            editor.text = "some text"
            await pilot.press("escape")
            assert editor.text == ""
            mock_tmux.send_raw.assert_not_called()

    async def test_escape_empty_forwards_to_agent(
        self, app: CompanionApp, mock_tmux: MagicMock
    ) -> None:
        async with app.run_test() as pilot:
            await pilot.press("escape")
            # Empty Escape should forward to agent
            mock_tmux.send_raw.assert_called_once_with("%0", "\x1b")

    async def test_ctrl_c_always_forwards(self, app: CompanionApp, mock_tmux: MagicMock) -> None:
        async with app.run_test() as pilot:
            editor = app.query_one("#editor", InputArea)
            editor.text = "some text"
            await pilot.press("ctrl+c")
            # Ctrl+C always forwards, even with text
            mock_tmux.send_raw.assert_called_once_with("%0", "\x03")

    async def test_multiline_enter_sends_all(self, app: CompanionApp, mock_tmux: MagicMock) -> None:
        async with app.run_test() as pilot:
            editor = app.query_one("#editor", InputArea)
            editor.text = "line 1\nline 2\nline 3"
            await pilot.press("enter")
            await asyncio.sleep(_IME_DELAY)
            mock_tmux.submit_to_pane.assert_called_once_with("%0", "line 1\nline 2\nline 3")

    async def test_history_navigation_ctrl_up(
        self, app: CompanionApp, mock_tmux: MagicMock
    ) -> None:
        async with app.run_test() as pilot:
            editor = app.query_one("#editor", InputArea)
            # Populate history directly to avoid timer-dependent flakiness.
            app.history.add("first")
            app.history.add("second")

            await pilot.press("ctrl+up")
            assert editor.text == "second"
            await pilot.press("escape")
            await pilot.press("ctrl+up")
            assert editor.text == "second"

    async def test_up_down_empty_forwards_to_agent(
        self, app: CompanionApp, mock_tmux: MagicMock
    ) -> None:
        async with app.run_test() as pilot:
            await pilot.press("up")
            mock_tmux.send_keys.assert_called_with("%0", "Up")
            mock_tmux.send_keys.reset_mock()
            await pilot.press("down")
            mock_tmux.send_keys.assert_called_with("%0", "Down")

    async def test_paste_failure_rings_bell(self, app: CompanionApp, mock_tmux: MagicMock) -> None:
        mock_tmux.submit_to_pane.side_effect = RuntimeError("tmux error")
        async with app.run_test() as pilot:
            editor = app.query_one("#editor", InputArea)
            editor.text = "will fail"
            await pilot.press("enter")
            await asyncio.sleep(_IME_DELAY)
            assert editor.text == "will fail"
