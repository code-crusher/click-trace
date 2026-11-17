"""Tests for ``click.override_streams``, added for issue #2361.

The context manager makes Click's console output functions write to given
streams instead of ``sys.stdout`` and ``sys.stderr``, so Click can be embedded
in an application (such as a server with concurrent connections) without
patching private functions or swapping the process-global streams.
"""

from __future__ import annotations

import io
import sys
import threading
import typing as t

import pytest

import click


@click.command()
def _hello_cmd():
    """Say hello."""
    click.echo("I EXECUTED")


def test_echo_writes_to_overridden_stdout():
    out, err = io.StringIO(), io.StringIO()

    with click.override_streams(stdout=out, stderr=err):
        click.echo("hello")
        click.echo("oops", err=True)

    assert out.getvalue() == "hello\n"
    assert err.getvalue() == "oops\n"


def test_override_streams_restores_previous_streams():
    out = io.StringIO()

    with click.override_streams(stdout=out):
        click.echo("inside")

    click.echo("outside", nl=False)
    assert out.getvalue() == "inside\n"


def test_only_stdout_overridden():
    """Only the stream(s) passed are overridden; the other keeps its default."""
    out = io.StringIO()

    with click.override_streams(stdout=out):
        click.echo("hello")

    assert out.getvalue() == "hello\n"


def test_only_stderr_overridden():
    err = io.StringIO()

    with click.override_streams(stderr=err):
        click.echo("oops", err=True)

    assert err.getvalue() == "oops\n"


def test_override_streams_not_active_after_exception():
    out = io.StringIO()

    with pytest.raises(RuntimeError), click.override_streams(stdout=out):
        click.echo("before failure")
        raise RuntimeError

    out.write("after")
    assert out.getvalue() == "before failure\nafter"


def test_nested_overrides_use_innermost():
    outer, inner = io.StringIO(), io.StringIO()

    with click.override_streams(stdout=outer):
        click.echo("outer")
        with click.override_streams(stdout=inner):
            click.echo("inner")
        click.echo("outer again")

    assert outer.getvalue() == "outer\nouter again\n"
    assert inner.getvalue() == "inner\n"


def test_explicit_file_argument_wins():
    """An explicit ``file`` argument is not affected by the override."""
    out, explicit = io.StringIO(), io.StringIO()

    with click.override_streams(stdout=out):
        click.echo("default", file=explicit)

    assert explicit.getvalue() == "default\n"
    assert out.getvalue() == ""


def test_command_output_respects_override():
    out = io.StringIO()

    with click.override_streams(stdout=out):
        _hello_cmd.main([], standalone_mode=False)

    assert out.getvalue() == "I EXECUTED\n"


def test_help_output_respects_override():
    """The default help option callback writes through ``echo`` with no
    explicit file, so its output respects the override. This was one of
    the non-accessible internal usages named in the issue.
    """
    out = io.StringIO()

    with click.override_streams(stdout=out):
        with pytest.raises(SystemExit) as exc_info:
            _hello_cmd.main(["--help"], standalone_mode=True)

    assert exc_info.value.code == 0
    assert "Say hello." in out.getvalue()
    assert "Show this message and exit." in out.getvalue()


def test_usage_error_respects_override():
    """Click's error output (``UsageError.show``) respects the override."""
    out = io.StringIO()

    with click.override_streams(stdout=out, stderr=out):
        with pytest.raises(SystemExit) as exc_info:
            _hello_cmd.main(["--bogus"], standalone_mode=True)

    assert exc_info.value.code == 2
    assert "No such option '--bogus'." in out.getvalue()


def test_click_exception_respects_override():
    """``ClickException.show`` writes to the default stderr, which is
    overridden.
    """

    @click.command()
    def cli():
        raise click.ClickException("exploded")

    out = io.StringIO()

    with click.override_streams(stdout=out, stderr=out):
        with pytest.raises(SystemExit) as exc_info:
            cli.main([], standalone_mode=True)

    assert exc_info.value.code == 1
    assert "Error: exploded" in out.getvalue()


def test_abort_message_respects_override():
    """The ``Aborted!`` message written by ``main()`` respects the
    override, instead of going to the process-global ``sys.stderr``.
    """

    @click.command()
    def cli():
        raise click.Abort()

    out = io.StringIO()

    with click.override_streams(stdout=out, stderr=out):
        with pytest.raises(SystemExit):
            cli.main([], standalone_mode=True)

    assert "Aborted!" in out.getvalue()


def test_interrupt_message_respects_override(monkeypatch):
    """A ``KeyboardInterrupt`` during ``main()`` writes the blank line
    that closes the terminal's ``^C`` echo to the overridden stderr.
    """

    @click.command()
    def cli():
        raise KeyboardInterrupt

    out = io.StringIO()

    with click.override_streams(stdout=out, stderr=out):
        with pytest.raises(SystemExit):
            cli.main([], standalone_mode=True)

    assert out.getvalue() == "\nAborted!\n"


def test_progressbar_respects_override():
    out = io.StringIO()

    with click.override_streams(stdout=out):
        with click.progressbar(range(3), label="working") as bar:
            for _ in bar:
                pass

    assert "working" in out.getvalue()


def test_echo_via_pager_respects_override():
    """With no tty, the pager falls back to writing to the default
    stdout, which is overridden.
    """
    out = io.StringIO()

    with click.override_streams(stdout=out):
        click.echo_via_pager("paged text\n")

    assert "paged text" in out.getvalue()


def _make_input_mock(answers: list[str]) -> t.Callable[[str], str]:
    """A ``visible_prompt_func`` stand-in that behaves like ``input()``:
    it writes the prompt to ``sys.stdout`` and returns the next answer.
    """
    iterator = iter(answers)

    def func(prompt: str) -> str:
        sys.stdout.write(prompt)
        return next(iterator)

    return func


def test_prompt_respects_override(monkeypatch):
    """The prompt text is written to the overridden stdout, not to the
    real ``sys.stdout`` that ``input()`` would use.
    """
    out = io.StringIO()
    monkeypatch.setattr(
        click.termui, "visible_prompt_func", _make_input_mock(["typed"])
    )

    with click.override_streams(stdout=out):
        value = click.prompt("What is your name")

    assert value == "typed"
    assert out.getvalue() == "What is your name: "


def test_prompt_err_respects_override(monkeypatch):
    """A prompt with ``err=True`` writes to the overridden stderr."""
    err = io.StringIO()
    monkeypatch.setattr(
        click.termui, "visible_prompt_func", _make_input_mock(["typed"])
    )

    with click.override_streams(stdout=io.StringIO(), stderr=err):
        value = click.prompt("Question", err=True)

    assert value == "typed"
    assert err.getvalue() == "Question: "


def test_confirm_respects_override(monkeypatch):
    out = io.StringIO()
    monkeypatch.setattr(click.termui, "visible_prompt_func", _make_input_mock(["y"]))

    with click.override_streams(stdout=out):
        value = click.confirm("Proceed?")

    assert value is True
    assert out.getvalue() == "Proceed? [y/N]: "


def test_prompt_error_message_respects_override(monkeypatch):
    """A value that fails conversion prints an error through the
    overridden stream, then re-asks.
    """
    out = io.StringIO()
    monkeypatch.setattr(
        click.termui, "visible_prompt_func", _make_input_mock(["bad", "3"])
    )

    with click.override_streams(stdout=out):
        value = click.prompt("Number", type=int)

    assert value == 3
    assert "Error: " in out.getvalue()
    assert out.getvalue().count("Number: ") == 2


def test_concurrent_threads_use_their_own_streams():
    """Each thread sees its own streams: no output leaks between the
    concurrent "connections", which was the original problem.
    """
    n = 100
    buffers = {name: io.StringIO() for name in "abcd"}
    barrier = threading.Barrier(len(buffers))

    def run(name: str, buf: io.StringIO) -> None:
        # Each handler sets its own streams inside the thread.
        with click.override_streams(stdout=buf, stderr=buf):
            barrier.wait()
            for _ in range(n):
                click.echo(name)

    threads = [
        threading.Thread(target=run, args=(name, buf)) for name, buf in buffers.items()
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    for name, buf in buffers.items():
        lines = buf.getvalue().splitlines()
        assert len(lines) == n
        assert set(lines) == {name}


def test_copy_context_runs_with_same_streams():
    """The issue's server example runs ``main`` in a copied context; the
    override is part of the context and carries into ``Context.run()``.
    """
    from contextvars import copy_context

    out = io.StringIO()

    with click.override_streams(stdout=out):
        context = copy_context()
        context.run(_hello_cmd.main, [], standalone_mode=False)

    assert out.getvalue() == "I EXECUTED\n"


def test_cli_runner_captures_output_inside_override(monkeypatch):
    """``CliRunner`` replaces ``sys.stdout``; an override set outside it
    still applies because it wins over whatever ``sys.stdout`` is at the
    time of the call.
    """
    from click.testing import CliRunner

    out = io.StringIO()
    runner = CliRunner()

    with click.override_streams(stdout=out):
        result = runner.invoke(_hello_cmd, [])

    # The override wins: output went to the override, not the runner's
    # captured streams.
    assert out.getvalue() == "I EXECUTED\n"
    assert result.output == ""


def test_context_manager_does_not_close_streams():
    """Click must not close the borrowed streams when the block ends."""
    out = io.StringIO()

    with click.override_streams(stdout=out):
        click.echo("hello")

    assert not out.closed
    out.write("still writable")
    assert out.getvalue() == "hello\nstill writable"
