# Status Relay

Status Relay is a small command-line service health checker. It makes HTTPS
requests to configured endpoints, compares the response status with the expected
codes, and writes a JSON summary suitable for a job or monitoring script.

This repository is a demonstration maintained by the AI Code Guardian
maintainer. Its pull request workflow uses
[AI Code Guardian v1.1.0](https://github.com/msol3sco/ai-code-guardian/releases/tag/v1.1.0)
to scan changed lines, annotate findings, and save a SARIF report. Guardian
reads source files without running Status Relay. The unit tests replace all
HTTP calls with controlled test responses.

## Install and run

Use Python 3.10 or later in an activated virtual environment.

```sh
python -m pip install .
python -m unittest discover -s tests -v
status-relay --config examples/probes.json
```

Replace the sample URLs with endpoints you operate before using this as a
health check. The sample uses a reserved `.invalid` domain for the readiness
probe and will report a connection failure for it if run unchanged.

Each probe requires a unique name and an HTTPS URL. You can customize its
timeout and expected HTTP status codes. The default is five seconds and
HTTP 200. Probes run sequentially, do not follow redirects, and do not read
response bodies. The output contains a status or failure category and
elapsed time. Endpoints and exception details are kept out of the JSON report.

| Exit code | Meaning |
| --- | --- |
| 0 | All probes matched their expected status. |
| 1 | At least one probe failed its health check. |
| 2 | Invalid command usage or configuration. |

See the [AI Code Guardian repository](https://github.com/msol3sco/ai-code-guardian)
for installation and configuration of the scanner.
