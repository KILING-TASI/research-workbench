# Evidence-based research workbench

Organize company, fund, ETF and macro research, retain evidence and reports, and optionally invoke explicitly configured professional engines. New disclosure worksheets distinguish forecasts, shareholder observations, plans and implementation.

[中文说明](README.md) · [Release v0.1.0-beta.21](https://github.com/KILING-TASI/research-workbench/releases/tag/v0.1.0-beta.21) · [Skill instructions](SKILL.md) · [Input preparation](BEGINNER.md)

Current release: **beta prerelease**. Python **3.11+**. Base runtime dependencies: none.

## First run

Download the [complete source ZIP](https://github.com/KILING-TASI/research-workbench/releases/download/v0.1.0-beta.21/research-workbench-v0.1.0-beta.21-source.zip), extract it and enter the directory containing `try_demo.py`:

```console
python try_demo.py --no-open --out-dir reports/first-demo
```

Alternatively, clone `https://github.com/KILING-TASI/research-workbench.git`, run `cd research-workbench`, then execute the command above. Open the report at the path printed by the command. Teaching data is synthetic; use a new output directory and keep prior reports.

## CLI and Skill

From the source directory:

```console
python -m pip install .
research-workbench --help
```

Repository and distribution: `research-workbench`. Primary CLI: `research-workbench`. Skill name in SKILL.md: `research-workbench`. Installing the CLI does not register the Skill; configure the complete resources in an assistant that supports local Skills. Build or optional dependencies may require network access during installation.

## Scope and rights

Read the [Chinese capability boundaries](README.md#能力与边界) and [detailed commands](USAGE.md). Each tool can run independently; cross-tool calls need explicit configuration. Successful execution does not authenticate source documents, fill missing data or establish investment validity. No trade execution or guaranteed returns.

Original code uses MIT. Third-party code and documents/data retain their own licenses and rights. Default-branch documentation edits do not rewrite released archives or frozen results.

[Changes](CHANGELOG.md) · [Third-party rights](THIRD_PARTY_NOTICES.md) · [Contribution](CONTRIBUTING.md) · [Security](SECURITY.md)
