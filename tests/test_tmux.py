"""Tests for tmux utility functions."""

from __future__ import annotations

import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from tui_input.tmux import (
    TmuxCommandError,
    TmuxNotInstalledError,
    _run_tmux,
    cancel_copy_mode,
    current_pane_id,
    ensure_tmux_installed,
    in_tmux,
    pane_exists,
    pane_height,
    pane_width,
    paste_to_pane,
    rejoin_companion,
    resize_pane,
    send_keys,
    set_hook,
    split_window,
    submit_to_pane,
    unset_hook,
)


class TestEnsureTmuxInstalled:
    def test_raises_when_tmux_not_found(self) -> None:
        with (
            patch("tui_input.tmux.shutil.which", return_value=None),
            pytest.raises(TmuxNotInstalledError, match="tmux is required"),
        ):
            ensure_tmux_installed()

    def test_passes_when_tmux_found(self) -> None:
        with patch("tui_input.tmux.shutil.which", return_value="/usr/bin/tmux"):
            ensure_tmux_installed()


class TestInTmux:
    def test_returns_true_when_tmux_env_set(self) -> None:
        with patch.dict(os.environ, {"TMUX": "/tmp/tmux-1000/default,12345,0"}):
            assert in_tmux() is True

    def test_returns_false_when_tmux_env_not_set(self) -> None:
        env = os.environ.copy()
        env.pop("TMUX", None)
        with patch.dict(os.environ, env, clear=True):
            assert in_tmux() is False


class TestRunTmux:
    def test_returns_stripped_stdout(self) -> None:
        mock_result = MagicMock()
        mock_result.stdout = "  %3  \n"
        with patch("tui_input.tmux.subprocess.run", return_value=mock_result) as mock_run:
            result = _run_tmux("display-message", "-p", "#{pane_id}")
            assert result == "%3"
            mock_run.assert_called_once_with(
                ["tmux", "display-message", "-p", "#{pane_id}"],
                capture_output=True,
                text=True,
                check=True,
            )

    def test_raises_tmux_command_error_on_failure(self) -> None:
        with (
            patch(
                "tui_input.tmux.subprocess.run",
                side_effect=subprocess.CalledProcessError(1, "tmux", stderr="bad pane"),
            ),
            pytest.raises(TmuxCommandError, match="tmux command failed"),
        ):
            _run_tmux("display-message", "-t", "%99")


class TestCurrentPaneId:
    def test_returns_pane_id(self) -> None:
        with patch("tui_input.tmux._run_tmux", return_value="%5") as mock:
            assert current_pane_id() == "%5"
            mock.assert_called_once_with("display-message", "-p", "#{pane_id}")


class TestSplitWindow:
    def test_split_without_command(self) -> None:
        with patch("tui_input.tmux._run_tmux", return_value="%7") as mock:
            result = split_window(3)
            assert result == "%7"
            mock.assert_called_once_with("split-window", "-v", "-l", "3", "-P", "-F", "#{pane_id}")

    def test_split_with_command(self) -> None:
        with patch("tui_input.tmux._run_tmux", return_value="%8") as mock:
            result = split_window(5, "echo hello")
            assert result == "%8"
            mock.assert_called_once_with(
                "split-window", "-v", "-l", "5", "-P", "-F", "#{pane_id}", "echo hello"
            )


class TestSendKeys:
    def test_sends_keys_to_pane(self) -> None:
        with patch("tui_input.tmux._run_tmux") as mock:
            send_keys("%3", "hello")
            mock.assert_called_once_with("send-keys", "-t", "%3", "hello")


class TestPasteToPane:
    def test_loads_and_pastes_buffer(self) -> None:
        calls: list[tuple[str, ...]] = []

        def fake_run_tmux(*args: str) -> str:
            calls.append(args)
            return ""

        with (
            patch("tui_input.tmux._run_tmux", side_effect=fake_run_tmux),
            patch("tui_input.tmux.os.unlink") as mock_unlink,
        ):
            paste_to_pane("%3", "hello world")

            assert len(calls) == 2
            assert calls[0][0] == "load-buffer"
            tmp_path = calls[0][1]
            assert tmp_path.endswith(".txt")
            # Bracketed paste uses -p flag.
            assert calls[1] == ("paste-buffer", "-p", "-d", "-t", "%3")
            mock_unlink.assert_called_once_with(tmp_path)


class TestSubmitToPane:
    def test_paste_then_enter(self) -> None:
        """submit_to_pane should paste text and send Enter as separate operations."""
        calls: list[tuple[str, ...]] = []

        def fake_run_tmux(*args: str) -> str:
            calls.append(args)
            return ""

        with (
            patch("tui_input.tmux._run_tmux", side_effect=fake_run_tmux),
            patch("tui_input.tmux.os.unlink"),
        ):
            submit_to_pane("%3", "hello")

            # 3 calls: load-buffer, paste-buffer, send-keys Enter
            assert len(calls) == 3
            assert calls[0][0] == "load-buffer"
            assert calls[1] == ("paste-buffer", "-d", "-t", "%3")
            assert calls[2] == ("send-keys", "-t", "%3", "Enter")


class TestResizePane:
    def test_resizes_pane(self) -> None:
        with patch("tui_input.tmux._run_tmux") as mock:
            resize_pane("%3", 7)
            mock.assert_called_once_with("resize-pane", "-t", "%3", "-y", "7")


class TestPaneExists:
    def test_returns_true_when_pane_found(self) -> None:
        mock_result = MagicMock()
        mock_result.stdout = "%0\n%1\n%3\n"
        with patch("tui_input.tmux.subprocess.run", return_value=mock_result):
            assert pane_exists("%3") is True

    def test_returns_false_when_pane_not_found(self) -> None:
        mock_result = MagicMock()
        mock_result.stdout = "%0\n%1\n"
        with patch("tui_input.tmux.subprocess.run", return_value=mock_result):
            assert pane_exists("%3") is False

    def test_returns_false_on_error(self) -> None:
        with patch(
            "tui_input.tmux.subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "tmux"),
        ):
            assert pane_exists("%3") is False


class TestPaneHeight:
    def test_returns_height(self) -> None:
        with patch("tui_input.tmux._run_tmux", return_value="25") as mock:
            assert pane_height("%3") == 25
            mock.assert_called_once_with("display-message", "-t", "%3", "-p", "#{pane_height}")


class TestPaneWidth:
    def test_returns_width(self) -> None:
        with patch("tui_input.tmux._run_tmux", return_value="120") as mock:
            assert pane_width("%3") == 120
            mock.assert_called_once_with("display-message", "-t", "%3", "-p", "#{pane_width}")


class TestSetHook:
    def test_sets_hook(self) -> None:
        with patch("tui_input.tmux._run_tmux") as mock:
            set_hook("after-split-window", "echo hi", "%0")
            mock.assert_called_once_with(
                "set-hook", "-w", "-t", "%0", "after-split-window", "echo hi"
            )


class TestUnsetHook:
    def test_unsets_hook(self) -> None:
        with patch("tui_input.tmux._run_tmux") as mock:
            unset_hook("after-split-window", "%0")
            mock.assert_called_once_with("set-hook", "-u", "-w", "-t", "%0", "after-split-window")


class TestRejoinCompanion:
    def test_joins_pane(self) -> None:
        with patch("tui_input.tmux._run_tmux") as mock:
            rejoin_companion("%0", "%1", 5)
            mock.assert_called_once_with("join-pane", "-v", "-s", "%1", "-t", "%0", "-l", "5")


class TestCancelCopyMode:
    def test_enters_and_cancels_copy_mode(self) -> None:
        calls: list[tuple[str, ...]] = []

        def fake_run_tmux(*args: str) -> str:
            calls.append(args)
            return ""

        with patch("tui_input.tmux._run_tmux", side_effect=fake_run_tmux):
            cancel_copy_mode("%5")

            assert len(calls) == 2
            assert calls[0] == ("copy-mode", "-t", "%5")
            assert calls[1] == ("send-keys", "-t", "%5", "-X", "cancel")
