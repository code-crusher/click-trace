import os
import pathlib
import platform
import subprocess
import sys
import tempfile
import typing as t

import pytest

import click


def test_path_dash_no_byteswarning():
    """Detecting the ``-`` dash sentinel must not compare ``bytes`` against
    ``str``, which raises a ``BytesWarning`` under ``python -bb``.

    The warning is only emitted when the interpreter runs with ``-b``, so this
    has to be checked in a subprocess. ``-bb`` turns the warning into an error,
    so a clean exit means no mismatched comparison happened.
    """
    program = (
        "import click\n"
        "convert = click.Path(allow_dash=True).convert\n"
        "for value in ('-', '', b'-', b''):\n"
        "    convert(value, None, None)\n"
    )
    result = subprocess.run(
        [sys.executable, "-bb", "-c", program],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "BytesWarning" not in result.stderr


def _symlinks_supported():
    with tempfile.TemporaryDirectory(prefix="click-pytest-") as tempdir:
        target = os.path.join(tempdir, "target")
        open(target, "w").close()
        link = os.path.join(tempdir, "link")

        try:
            os.symlink(target, link)
            return True
        except OSError:
            return False


@pytest.mark.skipif(
    not _symlinks_supported(), reason="The current OS or FS doesn't support symlinks."
)
def test_path_resolve_symlink(tmp_path, runner):
    test_file = tmp_path / "file"
    test_file_str = os.fspath(test_file)
    test_file.write_text("")

    path_type = click.Path(resolve_path=True)
    param = click.Argument(["a"], type=path_type)
    ctx = click.Context(click.Command("cli", params=[param]))

    test_dir = tmp_path / "dir"
    test_dir.mkdir()

    abs_link = test_dir / "abs"
    abs_link.symlink_to(test_file)
    abs_rv = path_type.convert(os.fspath(abs_link), param, ctx)
    assert abs_rv == test_file_str

    rel_link = test_dir / "rel"
    rel_link.symlink_to(pathlib.Path("..") / "file")
    rel_rv = path_type.convert(os.fspath(rel_link), param, ctx)
    assert rel_rv == test_file_str


def _non_utf8_filenames_supported():
    with tempfile.TemporaryDirectory(prefix="click-pytest-") as tempdir:
        try:
            f = open(os.path.join(tempdir, "\udcff"), "w")
        except OSError:
            return False

        f.close()
        return True


@pytest.mark.skipif(
    not _non_utf8_filenames_supported(),
    reason="The current OS or FS doesn't support non-UTF-8 filenames.",
)
def test_path_surrogates(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    type = click.Path(exists=True)
    path = pathlib.Path("\udcff")

    with pytest.raises(click.BadParameter, match="'�' does not exist"):
        type.convert(path, None, None)

    type = click.Path(file_okay=False)
    path.touch()

    with pytest.raises(click.BadParameter, match="'�' is a file"):
        type.convert(path, None, None)

    path.unlink()
    type = click.Path(dir_okay=False)
    path.mkdir()

    with pytest.raises(click.BadParameter, match="'�' is a directory"):
        type.convert(path, None, None)

    path.rmdir()

    def no_access(*args, **kwargs):
        """Test environments may be running as root, so we have to fake the result of
        the access tests that use os.access
        """
        p = args[0]
        assert p == path, f"unexpected os.access call on file not under test: {p!r}"
        return False

    path.touch()
    type = click.Path(readable=True)

    with pytest.raises(click.BadParameter, match="'�' is not readable"):
        with monkeypatch.context() as m:
            m.setattr(os, "access", no_access)
            type.convert(path, None, None)

    type = click.Path(readable=False, writable=True)

    with pytest.raises(click.BadParameter, match="'�' is not writable"):
        with monkeypatch.context() as m:
            m.setattr(os, "access", no_access)
            type.convert(path, None, None)

    type = click.Path(readable=False, executable=True)

    with pytest.raises(click.BadParameter, match="'�' is not executable"):
        with monkeypatch.context() as m:
            m.setattr(os, "access", no_access)
            type.convert(path, None, None)

    path.unlink()


def _non_utf8_filenames_supported():
    with tempfile.TemporaryDirectory(prefix="click-pytest-") as tempdir:
        try:
            f = open(os.path.join(tempdir, "\udcff"), "w")
        except OSError:
            return False

        f.close()
        return True


@pytest.mark.skipif(
    platform.system() == "Windows", reason="Filepath syntax differences."
)
def test_invalid_path_with_esc_sequence():
    with pytest.raises(click.BadParameter) as exc_info:
        with tempfile.TemporaryDirectory(prefix="my\ndir") as tempdir:
            click.Path(dir_okay=False).convert(tempdir, None, None)

    assert "my\\ndir" in exc_info.value.message


@pytest.mark.parametrize(
    ("cls", "expect"),
    [
        (None, "a/b/c.txt"),
        (str, "a/b/c.txt"),
        (bytes, b"a/b/c.txt"),
        (pathlib.Path, pathlib.Path("a", "b", "c.txt")),
    ],
)
def test_path_type(runner, cls, expect):
    cli = click.Command(
        "cli",
        params=[click.Argument(["p"], type=click.Path(path_type=cls))],
        callback=lambda p: p,
    )
    result = runner.invoke(cli, ["a/b/c.txt"], standalone_mode=False)
    assert result.exception is None
    assert result.return_value == expect


def test_path_converted_type_parameter_at_runtime():
    assert t.get_args(click.Path[pathlib.Path]) == (pathlib.Path,)


def test_path_exists_default_is_none():
    """The default skips the existence check, so a path that does not exist
    and a path that exists are both valid.
    """
    assert click.Path().exists is None
    assert click.Path(exists=False).exists is False
    assert click.Path(exists=True).exists is True


def test_path_exists_required(tmp_path):
    """``exists=True`` requires the path to exist."""
    type = click.Path(exists=True)

    with pytest.raises(click.BadParameter, match=r"file\.txt' does not exist"):
        type.convert(os.fspath(tmp_path / "file.txt"), None, None)

    existing = tmp_path / "file.txt"
    existing.write_text("")
    assert type.convert(os.fspath(existing), None, None) == os.fspath(existing)


def test_path_not_exists(tmp_path):
    """``exists=False`` requires the path not to exist, so that a program
    can create it without overwriting anything. See issue #1428.
    """
    type = click.Path(exists=False)

    missing = tmp_path / "file.txt"
    assert type.convert(os.fspath(missing), None, None) == os.fspath(missing)

    existing = tmp_path / "file.txt"
    existing.write_text("")
    with pytest.raises(click.BadParameter, match=r"file\.txt' already exists"):
        type.convert(os.fspath(existing), None, None)

    # The check applies to directories too.
    existing_dir = tmp_path / "dir"
    existing_dir.mkdir()
    with pytest.raises(click.BadParameter, match=r"dir' already exists"):
        type.convert(os.fspath(existing_dir), None, None)

    missing_dir = tmp_path / "dir2"
    assert type.convert(os.fspath(missing_dir), None, None) == os.fspath(missing_dir)


def test_path_exists_false_cli(runner, tmp_path):
    """End-to-end: ``exists=False`` rejects an existing path and accepts a
    missing one.
    """

    @click.command()
    @click.argument("dest", type=click.Path(exists=False))
    def cli(dest):
        click.echo(f"would create {dest}")

    existing = tmp_path / "file.txt"
    existing.write_text("")

    result = runner.invoke(cli, [os.fspath(tmp_path / "new.txt")])
    assert result.exit_code == 0
    assert "would create" in result.output

    result = runner.invoke(cli, [os.fspath(existing)])
    assert result.exit_code == 2
    assert "already exists" in result.output


def test_path_exists_none_skips_remaining_checks(tmp_path):
    """With the check skipped, a path that does not exist is accepted and
    the file/dir/permission checks are silently skipped as before.
    """
    type = click.Path(dir_okay=False)
    missing = tmp_path / "file.txt"
    assert type.convert(os.fspath(missing), None, None) == os.fspath(missing)


def test_path_exists_false_error_message_format(tmp_path):
    """The error uses the type's name and :func:`format_filename`, matching
    the other ``Path`` errors.
    """
    type = click.Path(file_okay=True, dir_okay=False, exists=False)
    existing_dir = tmp_path / "dir"
    existing_dir.mkdir()

    with pytest.raises(click.BadParameter) as exc_info:
        type.convert(os.fspath(existing_dir), None, None)

    assert exc_info.value.message == f"File '{existing_dir}' already exists."
