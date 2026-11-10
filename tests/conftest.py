import pytest

from click.testing import CliRunner


@pytest.fixture(autouse=True)
def _isolate_color_env(monkeypatch):
    """Keep color detection deterministic regardless of the test machine.

    ``NO_COLOR`` and ``FORCE_COLOR`` override color detection, so a developer
    running the suite with either set would otherwise see unrelated color
    tests fail.
    """
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("FORCE_COLOR", raising=False)


@pytest.fixture(scope="function")
def runner(request):
    return CliRunner()
