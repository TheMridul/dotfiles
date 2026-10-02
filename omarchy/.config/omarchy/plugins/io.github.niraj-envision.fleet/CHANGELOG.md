# Changelog

Fleet follows [Semantic Versioning](https://semver.org/). Git tags use the
same version prefixed with `v`.

## [1.2.0] - 2026-09-04

### Security

- Bound SSH capture, HTTP request bodies, WebSocket messages, QML status
  output, request threads, fan-out, terminal dimensions, host cardinality,
  transfers, query limits, and all user-selectable command deadlines.
- Store credentials exclusively in Secret Service and fail closed when the
  keyring is unavailable; the obsolete reversible credential file is never read.
- Pin every local executable used by the installer, launcher, bar widget,
  desktop integration, SSH, VPN, and theme paths instead of trusting inherited
  `PATH` lookup.
- Install and remove every payload/config file through a descriptor-bound,
  locked write-ahead transaction with durable backups, atomic replacement,
  concurrent-edit refusal, automatic rollback, and next-run crash recovery.
- Refuse symlinks, hard links, special files, unsafe owners/modes, oversized
  leaves, and writable ancestors before reading or replacing managed files.
- Record exact xterm.js upstream versions, tarball provenance, and SHA-256
  hashes for every vendored browser artifact.

### Changed

- Hyprland integration now uses exact managed markers, migrates the legacy
  snippets, validates the live configuration, and is removed transactionally.
- The bar widget invokes Fleet and setup helpers with fixed argv, bounds all
  retained remote text, and renders it explicitly as plain text.
- Align the canonical application version with the Marketplace manifest.

## [1.1.1] - 2026-08-31

### Changed

- Clicking the Fleet bar widget now opens a compact, theme-native network
  status panel instead of launching the full application immediately.
- The panel shows host connectivity and current CPU, memory, and disk summaries,
  with an explicit **Open full app** action for launching the full interface.

## [1.1.0] - 2026-08-31

### Added

- OpenVPN and WireGuard profiles, per-host routing, live tunnel status,
  credential handling, server overrides, and VPN regression coverage.
- Omarchy 4 semantic palette integration for current, legacy, dark, light,
  custom, and future themes.
- Live theme repainting for the application and embedded terminals.
- `fleet --version`, a canonical `VERSION` file, API version reporting, and a
  stock-theme compatibility matrix.

### Fixed

- Use Omarchy's current `omarchy-theme-color` command instead of an obsolete
  path that silently forced Fleet's fallback palette.
- Use the theme's semantic accent and accessible accent text across the UI.
- Detect real `NOPASSWD` sudo rules before choosing `sudo -n`; otherwise use
  the desktop polkit flow.
- Preserve actionable OpenVPN output when startup exits early.
- Give each OpenVPN profile a stable, typed TUN interface so route reporting,
  counters, and host badges reflect the kernel routing table.
- Focus Fleet's browser window specifically instead of any window whose title
  happens to contain “Fleet”.

[1.1.1]: https://github.com/niraj-envision/Fleet/releases/tag/v1.1.1
[1.1.0]: https://github.com/niraj-envision/Fleet/releases/tag/v1.1.0
[1.2.0]: https://github.com/niraj-envision/Fleet/releases/tag/v1.2.0
