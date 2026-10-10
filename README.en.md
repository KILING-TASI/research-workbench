# Evidence-based research workbench

Organize company, fund, ETF and macro research, retain evidence and reports, and optionally invoke explicitly configured professional engines. New disclosure worksheets distinguish forecasts, shareholder observations, plans and implementation.

[中文说明](README.md) · [Skill instructions](SKILL.md) · [First run](BEGINNER.md) · [Changes](CHANGELOG.md)

## Install and run

Clone this repository, enter its directory, and run `python -m pip install .`. Optional PDF or analysis components are documented in the Chinese README. To try the source-only teaching workflow without other repositories, run:

```console
python try_demo.py --no-open --out-dir reports/first-demo
```

Use a new output directory. Teaching data is synthetic; successful software execution does not verify original documents or complete data coverage. Installing the CLI does not automatically register the Skill: retain the complete repository resources when configuring the Skill in your assistant.

## Boundaries and rights

Each repository works independently; optional cross-repository calls need explicit configuration. Missing evidence stays unknown. No trade execution, profit guarantee, or institutional compliance certification is provided. Original code is MIT; third-party licenses and source-data rights remain separate. Do not redistribute source documents or data solely because the software uses MIT.
