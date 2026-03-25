Any change that alters the user-facing interface of this tool — new commands, new flags, changed defaults, new backends, changed behavior, or new/removed features — MUST also update:

1. **README.md** — Quick start, command table, backend list, and any affected sections
2. **COMMAND_REFERENCE.md** — Full command documentation, option tables, examples, architecture, key types
3. **GitHub About** — Run `gh repo edit` if the one-line project description needs updating

All three documentation targets plus the code changes go into the same commit. Push to remote after committing.

Changes that do NOT require documentation updates: bug fixes with no interface change, internal refactoring, test additions, code style.
