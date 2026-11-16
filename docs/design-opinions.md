# CLI Design Opinions

```{currentmodule} click
```
A penny for your thoughts...

```{contents}
:depth: 1
:local: true
```

## Options over arguments
{ref}`Positional arguments <arguments>` should be used sparingly, and if used should be required:
- The more positional arguments there are, the more confusing the CLI invocation becomes to read. (This is true of Python too.)
- Making some arguments optional, or arbitrary length, can make it harder to reason about. The parser handles this consistently by filling left to right, with an error if there is a non-optional unfilled after that. But that's not obvious to a user just looking at a command line.
- A command should be doing one thing, and the arguments should be related directly to that.
    - A group, where the argument is the sub-command name.
    - A command acts on some files.
    - A command looks at a source and acts on a destination.

## Variadic arguments should not be required
A {ref}`variadic argument <arguments>` (`nargs=-1`) takes an arbitrary
number of values, including none. By default it is not required, so a
command invoked with no values for it runs as a no-op. Setting
`required=True` makes it error unless at least one value is given, but
this is not recommended. Command line tools are often invoked with
wildcard inputs, and they should not error out if the wildcard expands
to nothing. Gracefully degrading into becoming a no-op is friendlier
in pipelines, where a command may legitimately receive no values.
