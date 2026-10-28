# Releasing

1. Update `__version__` in `src/fxtm/__init__.py` and move the entries in `CHANGELOG.md` under the new version.
2. Run the tests (`python -m unittest discover -s tests -v`) and check the browser app by hand once with real data
   (`fxtm serve`, load a recent day, play, place an order, open the report).
3. Commit, tag (`git tag v0.1.0`) and push the tag.
4. Create a GitHub release from the tag. The `Publish` workflow builds and uploads to PyPI.

## One-time PyPI setup

- Check that the name `fxtm` is free on pypi.org. If it is taken, change `name` in `pyproject.toml`
  (the command and the Python package can keep the name `fxtm`).
- On pypi.org add a trusted publisher for this repository: workflow `publish.yml`, environment `pypi`.
- In the GitHub repository create an environment called `pypi`.
- Fill in `[project.urls]` in `pyproject.toml`.

## Before the first public release

- Replace the placeholder owner in the issue and security notes, and decide the copyright holder in `LICENSE`.
- Re-read the Dukascopy terms of use and the "Data and legal" section of the README.
