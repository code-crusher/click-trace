import sys
from io import BytesIO
from io import StringIO

import pytest

import click._termui_impl
import click.utils
from click._compat import WIN


def test_echo(runner):
    with runner.isolation() as outstreams:
        click.echo("\N{SNOWMAN}")
        click.echo(b"\x44\x44")
        click.echo(42, nl=False)
        click.echo(b"a", nl=False)
        click.echo("\x1b[31mx\x1b[39m", nl=False)
        bytes = outstreams[0].getvalue().replace(b"\r\n", b"\n")
        assert bytes == b"\xe2\x98\x83\nDD\n42ax"

    # if wrapped, we expect bytes to survive.
    @click.command()
    def cli():
        click.echo(b"\xf6")

    result = runner.invoke(cli, [])
    assert result.stdout_bytes == b"\xf6\n"

    # Ensure we do not strip for bytes.
    with runner.isolation() as outstreams:
        click.echo(bytearray(b"\x1b[31mx\x1b[39m"), nl=False)
        assert outstreams[0].getvalue() == b"\x1b[31mx\x1b[39m"


def test_echo_custom_file():
    f = StringIO()
    click.echo("hello", file=f)
    assert f.getvalue() == "hello\n"

    b = BytesIO()
    click.echo(b"", b)
    assert b.getvalue() == b"\n"


def test_echo_no_streams(monkeypatch, runner):
    """echo should not fail when stdout and stderr are None with pythonw on Windows."""
    with runner.isolation():
        sys.stdout = None
        sys.stderr = None
        click.echo("test")
        click.echo("test", err=True)


def test_echo_with_capsys(capsys):
    click.echo("Capture me.")
    out, err = capsys.readouterr()
    assert out == "Capture me.\n"


def test_echo_color_flag(monkeypatch, capfd):
    isatty = True
    monkeypatch.setattr(click._compat, "isatty", lambda x: isatty)

    text = "foo"
    styled_text = click.style(text, fg="red")
    assert styled_text == "\x1b[31mfoo\x1b[0m"

    click.echo(styled_text, color=False)
    out, err = capfd.readouterr()
    assert out == f"{text}\n"

    click.echo(styled_text, color=True)
    out, err = capfd.readouterr()
    assert out == f"{styled_text}\n"

    click.echo(styled_text)
    out, err = capfd.readouterr()
    assert out == f"{styled_text}\n"

    isatty = False
    click.echo(styled_text)
    out, err = capfd.readouterr()
    assert out == f"{text}\n"

    click.echo(styled_text, color=True)
    out, err = capfd.readouterr()
    assert out == f"{styled_text}\n"


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({"FORCE_COLOR": "1"}, "\x1b[31mfoo\x1b[0m"),
        # Any non-empty value enables or disables color, matching the
        # Python interpreter's own handling of these variables.
        ({"FORCE_COLOR": "0"}, "\x1b[31mfoo\x1b[0m"),
        ({"NO_COLOR": "1"}, "foo"),
        # NO_COLOR takes precedence over FORCE_COLOR.
        ({"NO_COLOR": "1", "FORCE_COLOR": "1"}, "foo"),
    ],
)
def test_echo_env_color(monkeypatch, capfd, env, expected):
    """FORCE_COLOR keeps and NO_COLOR strips color when not a TTY."""
    monkeypatch.setattr(click._compat, "isatty", lambda x: False)

    for key, value in env.items():
        monkeypatch.setenv(key, value)

    click.echo(click.style("foo", fg="red"))
    out, err = capfd.readouterr()
    assert out == f"{expected}\n"


def test_echo_env_color_overridden_by_explicit_flag(monkeypatch, capfd):
    """An explicit color flag wins over the environment variables."""
    monkeypatch.setattr(click._compat, "isatty", lambda x: False)
    monkeypatch.setenv("FORCE_COLOR", "1")

    click.echo(click.style("foo", fg="red"), color=False)
    out, err = capfd.readouterr()
    assert out == "foo\n"

    monkeypatch.setenv("NO_COLOR", "1")
    click.echo(click.style("foo", fg="red"), color=True)
    out, err = capfd.readouterr()
    assert out == "\x1b[31mfoo\x1b[0m\n"


def test_echo_env_color_no_tty_check_forced(monkeypatch, capfd):
    """FORCE_COLOR enables color even when the stream is not a TTY."""
    monkeypatch.setattr(click._compat, "isatty", lambda x: False)
    monkeypatch.setenv("FORCE_COLOR", "1")

    click.secho("foo", fg="red")
    out, err = capfd.readouterr()
    assert out == "\x1b[31mfoo\x1b[0m\n"


@pytest.mark.skipif(WIN, reason="Test too complex to make work windows.")
def test_echo_writing_to_standard_error(capfd, monkeypatch):
    def emulate_input(text):
        """Emulate keyboard input."""
        monkeypatch.setattr(sys, "stdin", StringIO(text))

    click.echo("Echo to standard output")
    out, err = capfd.readouterr()
    assert out == "Echo to standard output\n"
    assert err == ""

    click.echo("Echo to standard error", err=True)
    out, err = capfd.readouterr()
    assert out == ""
    assert err == "Echo to standard error\n"

    emulate_input("asdlkj\n")
    click.prompt("Prompt to stdin")
    out, err = capfd.readouterr()
    assert out == "Prompt to stdin: "
    assert err == ""

    emulate_input("asdlkj\n")
    click.prompt("Prompt to stdin with no suffix", prompt_suffix="")
    out, err = capfd.readouterr()
    assert out == "Prompt to stdin with no suffix"
    assert err == ""

    # The full prompt goes through redirect_stdout so nothing leaks to stdout when
    # err=True.
    emulate_input("asdlkj\n")
    click.prompt("Prompt to stderr", err=True)
    out, err = capfd.readouterr()
    assert out == ""
    assert err == "Prompt to stderr: "

    emulate_input("asdlkj\n")
    click.prompt("Prompt to stderr with no suffix", prompt_suffix="", err=True)
    out, err = capfd.readouterr()
    assert out == ""
    assert err == "Prompt to stderr with no suffix"

    emulate_input("y\n")
    click.confirm("Prompt to stdin")
    out, err = capfd.readouterr()
    assert out == "Prompt to stdin [y/N]: "
    assert err == ""

    emulate_input("y\n")
    click.confirm("Prompt to stdin with no suffix", prompt_suffix="")
    out, err = capfd.readouterr()
    assert out == "Prompt to stdin with no suffix [y/N]"
    assert err == ""

    emulate_input("y\n")
    click.confirm("Prompt to stderr", err=True)
    out, err = capfd.readouterr()
    assert out == ""
    assert err == "Prompt to stderr [y/N]: "

    emulate_input("y\n")
    click.confirm("Prompt to stderr with no suffix", prompt_suffix="", err=True)
    out, err = capfd.readouterr()
    assert out == ""
    assert err == "Prompt to stderr with no suffix [y/N]"

    monkeypatch.setattr(click.termui, "isatty", lambda x: True)
    monkeypatch.setattr(click.termui, "getchar", lambda: " ")

    click.pause("Pause to stdout")
    out, err = capfd.readouterr()
    assert out == "Pause to stdout\n"
    assert err == ""

    click.pause("Pause to stderr", err=True)
    out, err = capfd.readouterr()
    assert out == ""
    assert err == "Pause to stderr\n"
