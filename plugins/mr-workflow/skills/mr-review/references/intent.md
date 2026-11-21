# Establishing intent

Read this before judging any code. The goal is to know what the change must achieve, in your own words, before you look at how.

## Sources, in priority order

1. **Linked issue or ticket** (`issues` in `context_file`, `source: closes` first). Its body holds the acceptance criteria.
2. **MR/PR description**: the "why" and the approach the author chose.
3. **Commit messages** (`commits`): the sequence of intent, and any "fix"/"revert" that changed direction.
4. **Title and branch name**: a summary only.
5. **The code itself**: confirms what was done, not what was meant.

When sources conflict, the linked ticket wins. Record the conflict as a finding.

## External tickets

`external_refs` lists keys like `ABC-123` that come from another tracker (Jira, Linear, and so on). They are not fetched.

- If you have a tool for that tracker (for example an MCP integration), fetch the key and read its acceptance criteria.
- Otherwise ask for criteria only when the goal cannot be understood or judged without them. Record nonessential unfetched tickets under "Not verified"; never guess criteria from the branch name.

## Intent card

Write this before reviewing the code. Five lines maximum:

```
Goal: <one sentence, what changes for the user or system>
Acceptance: <criteria from the ticket, or "none stated">
Non-goals: <what the MR explicitly does not do, or "none stated">
Approach: <the author's chosen design, one sentence>
Risks named by author: <from the description, or "none">
```

If "Acceptance" is "none stated" and the Goal is unclear, ask the user before reviewing.

## Requirement check

After reading the code, map each acceptance criterion to the code that meets it:

| Requirement | Status | Where | Evidence |
|-------------|--------|-------|----------|
| <criterion> | met / partial / missing / unclear | `path:line` | <one line: what the code does> |

- **met**: the code does it, and you checked the path it takes.
- **partial**: some cases or paths are not covered. Name which.
- **missing**: nothing in the diff does it.
- **unclear**: you cannot tell from the code. Say what would settle it.

## Approach check

Ask one question: is the chosen approach sound for this goal? Look for:

- a simpler way the code already supports (an existing helper, config, or pattern)
- a design that will fail under the load or data the goal implies
- a change that solves the symptom and not the cause named in the ticket

Report an approach problem as a finding only when you can name the alternative.

## Scope check

Changes outside the intent card are findings: unrelated refactors, drive-by changes, or features not in the ticket. Name the files. Do not treat them as bugs unless they break something.
