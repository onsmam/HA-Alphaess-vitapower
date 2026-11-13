# Releasing `alphaess-modbus-vitapower`

This document describes how to release a new version of `alphaess-modbus-vitapower` to PyPI.

## Tagging Convention

> [!IMPORTANT]
> **Release tags must be the bare semantic version prefixed with `library-`** (e.g. `library-0.1.5`, `library-1.0.0`).
> Do not use `v`-prefixed tags like `library-v0.1.5`.

This repository also releases the HACS integration, whose tags are bare versions; the prefix keeps the two apart. The publish workflow only runs for `library-` tags, strips the prefix and substitutes the rest into `pyproject.toml` to set the package version according to PEP 440.

## Release Process

1. **Verify CI**: Ensure that the `Library CI` workflow is green on the `main` branch.
2. **Draft a GitHub Release**:
   - Go to GitHub Releases: **Draft a new release**.
   - **Choose a tag**: Enter the new version number as a prefixed tag (e.g. `library-0.1.5`).
   - **Target**: `main`.
   - **Title**: Enter the version number (e.g. `alphaess-modbus-vitapower 0.1.5`).
   - **Description**: Provide release notes / changelog.
   - Leave **Set as the latest release** unticked, so HACS keeps offering the integration's latest release.
3. **Publish the Release**:
   - Click **Publish release**.
   - The `.github/workflows/library-publish.yml` workflow will automatically trigger, build the wheel and source distribution, and publish the package to PyPI via Trusted Publishing.

The first release needs a PyPI project with this repository and the `library-publish.yml` workflow (environment `pypi`) registered as its trusted publisher.
