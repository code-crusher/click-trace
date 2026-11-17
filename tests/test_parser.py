import pytest

import click
from click.parser import _OptionParser
from click.shell_completion import split_arg_string


@pytest.mark.parametrize(
    ("value", "expect"),
    [
        ("cli a b c", ["cli", "a", "b", "c"]),
        ("cli 'my file", ["cli", "my file"]),
        ("cli 'my file'", ["cli", "my file"]),
        ("cli my\\", ["cli", "my"]),
        ("cli my\\ file", ["cli", "my file"]),
    ],
)
def test_split_arg_string(value, expect):
    assert split_arg_string(value) == expect


def test_parser_default_prefixes():
    parser = _OptionParser()
    assert parser._opt_prefixes == {"-", "--"}


def test_parser_collects_prefixes():
    ctx = click.Context(click.Command("test"))
    parser = _OptionParser(ctx)
    click.Option("+p", is_flag=True).add_to_parser(parser, ctx)
    click.Option("!e", is_flag=True).add_to_parser(parser, ctx)
    assert parser._opt_prefixes == {"-", "--", "+", "!"}


def test_parser_resilient_keeps_arguments_after_option_error():
    # Issue #2184: an option error, such as an option missing its value at
    # the end of the line, must not discard positional values parsed before
    # it while parsing resiliently.
    cli = click.Command(
        "test", params=[click.Argument(["arg"]), click.Option(["--opt"])]
    )
    ctx = click.Context(cli, resilient_parsing=True)
    parser = cli.make_parser(ctx)
    opts, args, _ = parser.parse_args(["value", "--opt"])
    assert opts == {"arg": "value"}
    assert args == []


def test_parser_not_resilient_raises_option_error():
    cli = click.Command(
        "test", params=[click.Argument(["arg"]), click.Option(["--opt"])]
    )
    ctx = click.Context(cli)
    parser = cli.make_parser(ctx)

    with pytest.raises(click.UsageError, match="requires an argument"):
        parser.parse_args(["value", "--opt"])
