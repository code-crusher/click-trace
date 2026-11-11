"""The structured help data behind ``--help``.

``get_help_info`` exposes the same content the default help page renders,
as data, so a custom renderer does not have to know Click's internals.
"""

import pytest

import click


def make_command() -> click.Command:
    @click.command(
        help="Long help.\f\nIgnored after the form feed.",
        epilog="The epilog.",
    )
    @click.argument("name", help="Who to greet.")
    @click.argument("count", type=int)
    @click.option("--greeting", default="Hello", help="What to say.")
    @click.option("--secret", hidden=True, help="Not shown.")
    def cli(name: str, count: int, greeting: str, secret: str) -> None:
        pass

    return cli


def test_command_help_info():
    cli = make_command()
    ctx = click.Context(cli, info_name="cli")
    info = cli.get_help_info(ctx)

    assert info["usage"] == "Usage: cli [OPTIONS] NAME COUNT"
    assert info["help"] == "Long help."
    assert info["epilog"] == "The epilog."
    assert info["options"] == [
        {"spec": "--greeting TEXT", "help": "What to say."},
        {"spec": "--help", "help": "Show this message and exit."},
    ]
    assert info["arguments"] == [
        {"spec": "NAME", "help": "Who to greet."},
        {"spec": "COUNT", "help": ""},
    ]
    assert info["commands"] == []


def test_context_help_info():
    cli = make_command()
    ctx = click.Context(cli, info_name="cli")
    assert ctx.get_help_info() == cli.get_help_info(ctx)


def test_empty_sections_are_empty_lists():
    cli = click.Command("cli")
    ctx = click.Context(cli, info_name="cli")
    info = cli.get_help_info(ctx)

    assert info["help"] == ""
    assert info["epilog"] == ""
    assert info["arguments"] == []
    # The automatic help option is still listed.
    assert info["options"] == [
        {"spec": "--help", "help": "Show this message and exit."}
    ]


def test_arguments_section_omitted_without_documented_argument():
    """An undocumented argument gets no section, matching the rendered page."""
    cli = click.Command("cli", params=[click.Argument(["name"])])
    ctx = click.Context(cli, info_name="cli")

    assert cli.get_help_info(ctx)["arguments"] == []
    assert "Positional arguments" not in cli.get_help(ctx)


def test_deprecated_label_in_help_text():
    cli = click.Command("cli", help="Old.", deprecated="USE OTHER")
    ctx = click.Context(cli, info_name="cli")

    assert cli.get_help_info(ctx)["help"] == "Old. (DEPRECATED: USE OTHER)"


def test_group_help_info_commands():
    @click.group()
    def cli() -> None:
        pass

    @cli.command()
    def shown() -> None:
        """Shown help."""

    @cli.command(hidden=True)
    def hidden() -> None:
        """Hidden help."""

    ctx = click.Context(cli, info_name="cli")
    info = cli.get_help_info(ctx)

    assert info["commands"] == [{"spec": "shown", "help": "Shown help."}]


def test_group_help_info_short_help_limit():
    """A renderer can ask for a different truncation length."""

    @click.group()
    def cli() -> None:
        pass

    @cli.command()
    def sub() -> None:
        """This is a long help text that is truncated."""

    ctx = click.Context(cli, info_name="cli")
    rows = cli.get_help_commands(ctx, limit=10)

    assert rows[0]["help"].endswith("...")


def test_help_info_matches_rendered_help(runner):
    """Every non-empty piece of data appears on the default help page."""
    cli = make_command()
    info = cli.get_help_info(click.Context(cli, info_name="cli"))
    output = runner.invoke(cli, ["--help"], prog_name="cli").output

    assert info["usage"] in output
    assert info["help"] in output
    assert info["epilog"] in output

    for record in info["options"] + info["arguments"]:
        assert record["spec"] in output
        assert record["help"].split("  [")[0] in output


@pytest.mark.parametrize(
    ("method", "override"),
    [
        ("get_help_text", lambda ctx: "Replaced help."),
        ("get_help_epilog", lambda ctx: "Replaced epilog."),
    ],
)
def test_format_help_uses_help_info(runner, method, override):
    """Overriding a data getter changes the rendered help page."""
    cli = make_command()
    setattr(cli, method, override)

    output = runner.invoke(cli, ["--help"], prog_name="cli").output
    assert "Replaced" in output


def test_format_options_uses_help_info():
    """Overriding ``get_help_options`` changes the rendered options section."""
    cli = make_command()
    cli.get_help_options = lambda ctx: [
        click.core.HelpRecord(spec="--custom", help="Custom row.")
    ]

    output = cli.get_help(click.Context(cli, info_name="cli"))
    assert "--custom  Custom row." in output
    assert "--greeting" not in output


def test_format_commands_uses_help_info():
    """Overriding ``get_help_commands`` changes the rendered commands section."""

    @click.group()
    def cli() -> None:
        pass

    @cli.command()
    def sub() -> None:
        """Shown help."""

    cli.get_help_commands = lambda ctx, limit=45: [
        click.core.HelpRecord(spec="other", help="Other help.")
    ]

    output = cli.get_help(click.Context(cli, info_name="cli"))
    assert "other  Other help." in output
    assert "sub" not in output


def test_custom_renderer_builds_page_from_help_info():
    """A renderer that knows nothing about Click can lay out the data."""

    def render(info: click.HelpInfo) -> str:
        lines = [info["usage"], ""]

        if info["help"]:
            lines += [info["help"], ""]

        for title, rows in (
            ("Arguments", info["arguments"]),
            ("Options", info["options"]),
            ("Commands", info["commands"]),
        ):
            if rows:
                lines.append(f"* {title}")
                lines += [f"  {row['spec']}: {row['help']}" for row in rows]
                lines.append("")

        if info["epilog"]:
            lines.append(info["epilog"])

        return "\n".join(lines)

    cli = make_command()
    page = render(cli.get_help_info(click.Context(cli, info_name="cli")))

    assert page.splitlines() == [
        "Usage: cli [OPTIONS] NAME COUNT",
        "",
        "Long help.",
        "",
        "* Arguments",
        "  NAME: Who to greet.",
        "  COUNT: ",
        "",
        "* Options",
        "  --greeting TEXT: What to say.",
        "  --help: Show this message and exit.",
        "",
        "The epilog.",
    ]


def test_help_info_is_a_plain_dict():
    """The data serializes without custom encoders."""
    import json

    cli = make_command()
    info = cli.get_help_info(click.Context(cli, info_name="cli"))
    assert json.loads(json.dumps(info)) == info
