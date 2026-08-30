# Curated Incident Packages

BugSleuth supports a portable package layout for trusted demonstrations and regression investigations:

```text
INC-YYYY-NNN/
├── incident.json       # title, impact, and incident metadata
├── logs/               # captured log files
├── source/             # known source snapshot
├── tests/              # regression tests
├── git/                # candidate patch or change material
└── reasoning/          # reviewed hypothesis and tribunal artefacts
```

Packages are for curated, reviewed content. User uploads and public GitHub repositories continue through the safe static-analysis workflow and are never executed by the application.
