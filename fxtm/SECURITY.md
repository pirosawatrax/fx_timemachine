# Security

`fxtm serve` listens on `127.0.0.1` only and rejects requests whose `Host` or `Origin` is not local,
so web pages on other sites cannot drive it. It has no accounts, no telemetry and sends no data anywhere
except the tick downloads you start.

Please report vulnerabilities privately (for example with GitHub's "Report a vulnerability" feature) rather than
in a public issue. Include the version (`fxtm --version`), your OS, and steps to reproduce.
