"""Tests for behaviors documented in the user guide as workarounds for
long-standing parser limitations (see pallets/click#2676, #2771, #2768, #928,
#1279). These pin the documented recipes so the docs cannot silently drift
from reality before the parser is rewritten.
"""

import pytest

import click


def test_negative_number_after_double_dash(runner):
    @click.command()
    @click.argument("number", type=click.INT)
    def cli(number):
        click.echo(number)

    result = runner.invoke(cli, ["--", "-1"])
    assert result.exit_code == 0
    assert result.output == "-1\n"


def test_negative_number_without_double_dash_is_an_error(runner):
    @click.command()
    @click.argument("number", type=click.INT)
    def cli(number):
        click.echo(number)

    result = runner.invoke(cli, ["-1"])
    assert result.exit_code != 0
    assert "No such option" in result.output


def test_ignore_unknown_options_accepts_negative_number(runner):
    @click.command(context_settings={"ignore_unknown_options": True})
    @click.argument("number", type=float)
    def cli(number):
        click.echo(number)

    result = runner.invoke(cli, ["-2.5"])
    assert result.exit_code == 0
    assert result.output == "-2.5\n"


def test_comma_separated_values_with_callback(runner):
    def split_commas(ctx, param, value):
        out = []
        for item in value:
            out.extend(part.strip() for part in item.split(",") if part.strip())
        return tuple(out)

    @click.command()
    @click.option("--tag", multiple=True, callback=split_commas)
    def cli(tag):
        click.echo(", ".join(tag))

    result = runner.invoke(cli, ["--tag", "a,b", "--tag", " c ", "--tag", "d"])
    assert result.exit_code == 0
    assert result.output == "a, b, c, d\n"


def test_param_opts_reported_for_non_identifier_declaration(runner):
    seen = []

    def record(ctx, param, value):
        if value is not None:
            seen.append((param.name, list(param.opts)))
        return value

    with pytest.warns(DeprecationWarning, match="not a valid Python identifier"):
        @click.command()
        @click.option("--foo.foo", expose_value=False, callback=record)
        def cli():
            click.echo("done")

    result = runner.invoke(cli, ["--foo.foo", "x"])
    assert result.exit_code == 0
    assert seen == [("", ["--foo.foo"])]


def test_explicit_identifier_name_keeps_name_and_opts(runner):
    seen = []

    def record(ctx, param, value):
        seen.append((param.name, list(param.opts)))
        return value

    @click.command()
    @click.option("--foo.foo", "foo_foo", expose_value=False, callback=record)
    def cli():
        click.echo("done")

    result = runner.invoke(cli, ["--foo.foo", "x"])
    assert result.exit_code == 0
    assert seen == [("foo_foo", ["--foo.foo"])]


def test_contextual_choice_dependent_on_eager_option(runner):
    class ChoiceFrom(click.ParamType):
        name = "choice"

        def __init__(self, source):
            self.source = source

        def convert(self, value, param, ctx):
            choices = list(self.source(ctx))
            if value not in choices:
                self.fail(
                    f"{value!r} is not one of {', '.join(choices)}", param, ctx
                )
            return value

    def record_choice(ctx, param, value):
        ctx.meta["choices"] = {"a": ["x"], "b": ["y", "z"]}[value]
        return value

    @click.command()
    @click.option(
        "--mode",
        type=click.Choice(["a", "b"]),
        default="a",
        is_eager=True,
        callback=record_choice,
    )
    @click.option("--tag", type=ChoiceFrom(lambda ctx: ctx.meta["choices"]))
    def cli(mode, tag):
        click.echo(f"mode={mode} tag={tag}")

    result = runner.invoke(cli, ["--mode", "b", "--tag", "y"])
    assert result.exit_code == 0
    assert result.output == "mode=b tag=y\n"

    # eager option runs before the dependent one even if given later
    result = runner.invoke(cli, ["--tag", "y", "--mode", "b"])
    assert result.exit_code == 0
    assert result.output == "mode=b tag=y\n"

    result = runner.invoke(cli, ["--mode", "b", "--tag", "x"])
    assert result.exit_code != 0
    assert "is not one of" in result.output


def test_normalize_argv_from_context(runner):
    def normalized_argv(command, ctx):
        argv = []
        for param in command.params:
            source = ctx.get_parameter_source(param.name)
            if source is None or source is click.ParameterSource.DEFAULT:
                continue
            value = ctx.params[param.name]
            if isinstance(param, click.Option):
                flag = param.opts[-1]
                if param.is_flag:
                    if value:
                        argv.append(flag)
                elif param.count:
                    argv.extend([flag] * value)
                elif param.multiple:
                    for item in value:
                        argv += [flag, str(item)]
                elif param.nargs != 1:
                    argv.append(flag)
                    argv.extend(str(v) for v in value)
                else:
                    argv += [flag, str(value)]
            else:
                argv.extend(str(v) for v in value)
        return argv

    @click.command()
    @click.option("--times", default=1, type=int)
    @click.option("-v", "--verbose", "verbose", count=True)
    @click.option("--item", "items", multiple=True)
    @click.argument("files", nargs=-1)
    @click.pass_context
    def cli(ctx, times, verbose, items, files):
        click.echo(" ".join(normalized_argv(ctx.command, ctx)))

    result = runner.invoke(
        cli, ["--item", "b", "-vv", "--times", "3", "--item", "a", "f1"]
    )
    assert result.exit_code == 0
    assert result.output == "--times 3 --verbose --verbose --item b --item a f1\n"

    result = runner.invoke(cli, ["f1"])
    assert result.exit_code == 0
    assert result.output == "f1\n"
