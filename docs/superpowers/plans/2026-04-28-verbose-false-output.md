# Verbose=false 출력 정리 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `verbose=false` 환경에서 list-skills/profile-skills 의 접힌 Bash 패널 노이즈를 제거하고 fenced code block 만 사용자에게 보이게 한다.

**Architecture:** 두 SKILL.md 의 출력 분기 섹션만 수정한다. `verbose=true` 분기는 그대로, `verbose=false` 분기에서만 `> /tmp/...` 로 stdout 을 리다이렉트하고 Read 후 verbatim 붙여넣기로 바꾼다. 스크립트 코드는 변경하지 않는다.

**Tech Stack:** Markdown (SKILL.md), 셸 리다이렉트.

---

## File Structure

- Modify: `skills/list-skills/SKILL.md` — Step 2 ("Display based on `verbose`") 재작성.
- Modify: `skills/profile-skills/SKILL.md` — "Output Rules" 섹션 재작성.
- 스크립트 변경 없음.

---

### Task 1: list-skills SKILL.md 출력 분기 갱신

**Files:**
- Modify: `skills/list-skills/SKILL.md` (Step 2 섹션 전체)

- [ ] **Step 1: 현재 Step 2 섹션 확인**

Run: `sed -n '27,36p' skills/list-skills/SKILL.md`

Expected: 현재 "Step 2: Display based on `verbose`" 섹션 내용이 보임.

- [ ] **Step 2: Step 2 섹션 교체**

`skills/list-skills/SKILL.md` 의 다음 블록:

````markdown
### Step 2: Display based on `verbose`

How the table reaches the user depends on their `verbose` setting (in `~/.claude/settings.json`). Long Bash tool results are collapsed to "+N lines (ctrl+o to expand)" unless `verbose: true`, so the right move differs:

1. **Read `~/.claude/settings.json`** (or `~/.claude/settings.local.json` if it overrides) once before deciding.
2. **If `verbose === true`** — the Bash result is shown in full. Just run the script and stay silent. Do not re-paste, summarize, or reformat.
3. **If `verbose !== true`** (false or absent) — paste the script's stdout **verbatim as a fenced code block** so the user can read the whole table without expanding.

Never add commentary before or after unless the user follows up.
````

을 다음으로 교체:

````markdown
### Step 2: Display based on `verbose`

How the table reaches the user depends on their `verbose` setting (in `~/.claude/settings.json`). Long Bash tool results are collapsed to "+N lines (ctrl+o to expand)" unless `verbose: true`, so the execution path differs:

1. **Read `~/.claude/settings.json`** (or `~/.claude/settings.local.json` if it overrides) once before deciding.

2. **If `verbose === true`** — run the script directly:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/list-skills/scripts/collect_skills.py"
   ```

   The Bash result panel shows the full table. Stay silent — do not re-paste, summarize, or reformat.

3. **If `verbose !== true`** (false or absent) — redirect stdout to a temp file so the Bash panel stays empty (no collapsed `+N lines` noise):

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/list-skills/scripts/collect_skills.py" > /tmp/list-skills-output.txt
   ```

   Then Read `/tmp/list-skills-output.txt` and paste its contents **verbatim as a fenced code block**. This becomes the user's only visible output. Don't rephrase or reformat.

   stderr is not redirected, so any script error stays visible in the Bash panel for debugging.

Never add commentary before or after unless the user follows up.
````

- [ ] **Step 3: 변경 검증 (사라진 문구)**

Run: `grep -n "the right move differs" skills/list-skills/SKILL.md || echo "REMOVED"`

Expected: `REMOVED` (옛 문구가 더 이상 없어야 함).

- [ ] **Step 4: 변경 검증 (추가된 문구)**

Run: `grep -n "/tmp/list-skills-output.txt" skills/list-skills/SKILL.md`

Expected: 두 줄 이상 매치 (코드 블록 + 본문 언급).

- [ ] **Step 5: Commit**

```bash
git add skills/list-skills/SKILL.md
git commit -m "feat(list-skills): redirect stdout when verbose=false to drop collapsed Bash panel"
```

---

### Task 2: profile-skills SKILL.md 출력 분기 갱신

**Files:**
- Modify: `skills/profile-skills/SKILL.md` ("Output Rules" 섹션)

- [ ] **Step 1: 현재 Output Rules 섹션 확인**

Run: `sed -n '30,41p' skills/profile-skills/SKILL.md`

Expected: 현재 "Output Rules" 섹션 내용이 보임 (verbose 분기 + `--detail` 안내).

- [ ] **Step 2: Output Rules 섹션 교체**

`skills/profile-skills/SKILL.md` 의 다음 블록:

````markdown
## Output Rules

How the report's table reaches the user depends on their Claude Code `verbose` setting (in `~/.claude/settings.json`). Long Bash tool results are collapsed to "+N lines (ctrl+o to expand)" unless `verbose: true`, so the right move differs:

1. **Read `~/.claude/settings.json`** (or `~/.claude/settings.local.json` if it overrides) once before deciding.
2. **If `verbose === true`** — the Bash result is shown in full. Just run the script and stay silent. Do not re-paste, summarize, or reformat; any text would just duplicate what the user already sees.
3. **If `verbose !== true`** (false or absent) — the Bash result is truncated in the UI. Paste the script's stdout **verbatim as a fenced code block** so the user can read the whole table without expanding. Don't rephrase or reformat — the script already produced a well-aligned table.

In either case, never add commentary before or after unless the user follows up.

When `--detail` is used, the script opens a browser automatically and keeps a server alive. After launching, just confirm the URL and that `Ctrl+C` stops it — no need to paste the report itself.
````

을 다음으로 교체:

````markdown
## Output Rules

How the report's table reaches the user depends on their Claude Code `verbose` setting (in `~/.claude/settings.json`). Long Bash tool results are collapsed to "+N lines (ctrl+o to expand)" unless `verbose: true`, so the execution path differs:

1. **Read `~/.claude/settings.json`** (or `~/.claude/settings.local.json` if it overrides) once before deciding.

2. **If `verbose === true`** — run the script directly:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/profile-skills/scripts/report.py" [OPTIONS]
   ```

   The Bash result panel shows the full table. Stay silent — do not re-paste, summarize, or reformat.

3. **If `verbose !== true`** (false or absent) — redirect stdout to a temp file so the Bash panel stays empty (no collapsed `+N lines` noise):

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/profile-skills/scripts/report.py" [OPTIONS] > /tmp/profile-skills-output.txt
   ```

   Then Read `/tmp/profile-skills-output.txt` and paste its contents **verbatim as a fenced code block**. This becomes the user's only visible output. Don't rephrase or reformat.

   stderr is not redirected, so any script error stays visible in the Bash panel for debugging.

In either case, never add commentary before or after unless the user follows up.

The `--detail` flag is an exception: the script opens a browser and keeps a server alive, so do **not** redirect stdout. Run it directly regardless of `verbose`, then confirm the URL and that `Ctrl+C` stops it — no need to paste anything.
````

- [ ] **Step 3: 변경 검증 (사라진 문구)**

Run: `grep -n "the right move differs" skills/profile-skills/SKILL.md || echo "REMOVED"`

Expected: `REMOVED`.

- [ ] **Step 4: 변경 검증 (추가된 문구)**

Run: `grep -n "/tmp/profile-skills-output.txt" skills/profile-skills/SKILL.md`

Expected: 두 줄 이상 매치.

- [ ] **Step 5: 변경 검증 (`--detail` 예외 유지)**

Run: `grep -n "\-\-detail" skills/profile-skills/SKILL.md`

Expected: `--detail` 언급이 새 텍스트에서 살아있음 ("exception: ... do not redirect stdout").

- [ ] **Step 6: Commit**

```bash
git add skills/profile-skills/SKILL.md
git commit -m "feat(profile-skills): redirect stdout when verbose=false to drop collapsed Bash panel"
```

---

## Self-Review 결과

- **Spec coverage:** 스펙의 verbose=true(변경 없음) / verbose=false(redirect+Read+fenced) / `--detail` 예외 / stderr 비리다이렉트 — 모두 Task 1·2 에 들어감.
- **Placeholder scan:** TBD/TODO 없음. 코드 블록 모두 완전.
- **Type consistency:** 파일 경로(`/tmp/list-skills-output.txt`, `/tmp/profile-skills-output.txt`)와 스크립트 경로 모두 일관.
