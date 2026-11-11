from typing_extensions import assert_type

import click


@click.command()
@click.argument("name")
def hello(name: str) -> None:
    """Say hello."""


ctx = click.Context(hello)

info = hello.get_help_info(ctx)
assert_type(info, click.HelpInfo)
assert_type(info["usage"], str)
assert_type(info["help"], str)
assert_type(info["epilog"], str)
assert_type(info["options"], list[click.HelpRecord])
assert_type(info["arguments"], list[click.HelpRecord])
assert_type(info["commands"], list[click.HelpRecord])

assert_type(ctx.get_help_info(), click.HelpInfo)
