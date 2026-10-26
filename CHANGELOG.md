# Changelog

All notable changes to OKC Metal Weekly will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.0] - 2026-10-26

### Added
- Historical architecture documentation and ADR-0001.
- Automated pytest tests covering core data transformations.
- GitHub Actions CI for pushes and pull requests.
- Development dependency configuration.
- Support for optional show notations.
- Automatic pagination for Singles.

### Changed
- Improved date badge and notation placement.
- Extended the configurable publication window.

### Fixed
- Overlapping show notation labels.
- Singles overflowing a single slide.

## [0.4.0] - Historical release

### Added
- Configurable film grain, static texture, and vignette effects.
- Configurable image processing for the OKC background photograph.
- Distressed accent rules, rotated stamps, and venue labels.
- Distinct visual styling for Albums/EPs and Singles slides.
- Configurable color palettes and custom font support.

### Existing functionality
- Google Sheets integration for Shows and Releases.
- Python-based filtering and data preparation.
- Jinja2 HTML templates and Playwright PNG generation.
- PowerShell execution wrapper.
- GitHub Actions workflow for cloud-based generation.

### Notes
- Version 0.4.0 was tagged retrospectively at commit `33ff603`.
- Earlier development versions were not formally tagged.
- The v0.4 architecture will be documented separately.

[Unreleased]: https://github.com/erikvvargas/okc-metal-weekly/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/erikvvargas/okc-metal-weekly/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/erikvvargas/okc-metal-weekly/releases/tag/v0.4.0
