# Incident: skill validator cannot decode UTF-8 on Windows

## Fingerprint

`quick_validate.py` failed with `UnicodeDecodeError: 'gbk' codec can't decode byte` while reading a Chinese UTF-8 `SKILL.md`.

## Environment

- Windows PowerShell
- Miniconda Python 3.12 using the process default locale
- Codex `skill-creator/scripts/quick_validate.py`

## Symptoms

The validator stopped before checking frontmatter. The skill file itself was valid UTF-8 and readable by PowerShell.

## Root cause

The validator calls `Path.read_text()` without an explicit encoding. This Python process selected GBK from the Windows locale, while repository Markdown is UTF-8.

## Attempts that did not work

None. The stack trace identified the failing decode boundary directly.

## Resolution

Set `PYTHONUTF8=1` for the validator process:

```powershell
$env:PYTHONUTF8='1'
# quick_validate.py ships with the external Codex skill-creator tool, not this repository.
# Substitute your own install location for <codex-home>.
python '<codex-home>/skills/.system/skill-creator/scripts/quick_validate.py' 'skills/she-ios-soft-orbit'
```

## Verification

The same validator returned `Skill is valid!` with UTF-8 mode enabled.

## Prevention

Run Python documentation validators with UTF-8 mode on Windows. Do not rewrite valid Chinese content to satisfy a locale-dependent reader.

## Skill decision

Keep as incident. The fingerprint and one-line recovery are sufficient; promote only if multiple repository tools show the same failure.
