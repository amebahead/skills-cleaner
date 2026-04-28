# Verbose=false 환경에서 list-skills / profile-skills 출력 정리

날짜: 2026-04-28
대상 스킬: `skills-cleaner:list-skills`, `skills-cleaner:profile-skills`

## 문제

현재 두 스킬의 SKILL.md는 `~/.claude/settings.json`의 `verbose` 설정을 읽어 분기한다.

- `verbose === true`: Bash 결과 패널이 그대로 보이므로 Claude는 침묵.
- `verbose !== true`: Bash 결과 패널이 `+N lines (ctrl+o to expand)` 로 접힘 → Claude가 동일 내용을 fenced code block으로 다시 붙여넣음.

`verbose=false` 분기에서 사용자에게는 **접힌 Bash 패널 + 동일 내용의 fenced block** 두 개가 보인다. 접힌 Bash 패널은 ctrl+o 를 눌러야 펼쳐지므로 사실상 노이즈고, fenced block 만 실제 표시 채널 역할을 한다.

## 목표

`verbose=false` 일 때, Bash 결과 패널 자체를 띄우지 않고 Claude의 텍스트 응답(fenced code block) 만 사용자에게 보이게 한다. `verbose=true` 동작은 변경하지 않는다.

## 설계

SKILL.md의 출력 분기를 다음과 같이 수정한다. 스크립트 코드는 변경하지 않는다 (셸 리다이렉트만 사용).

### verbose=true 분기 (변경 없음)

list-skills 예:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/list-skills/scripts/collect_skills.py"
```

- Bash 결과 패널이 전체 출력을 그대로 보여줌.
- Claude는 추가 텍스트를 출력하지 않음.

### verbose=false 분기 (신규)

list-skills 예:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/list-skills/scripts/collect_skills.py" > /tmp/list-skills-output.txt
```

profile-skills 예:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/profile-skills/scripts/report.py" [OPTIONS] > /tmp/profile-skills-output.txt
```

1. 스크립트 stdout을 임시 파일로 리다이렉트 → Bash 결과 패널은 비어 있음 (접힐 게 없음).
2. Read 툴로 임시 파일을 읽어 Claude가 내용 확보.
3. 읽은 내용을 fenced code block 으로 verbatim 출력 → 사용자가 보는 메인 출력.

stderr는 리다이렉트하지 않는다. 스크립트 실행 중 에러가 발생하면 stderr가 Bash 결과 패널에 그대로 노출되어 디버깅이 가능해진다.

파일 경로:
- `list-skills` → `/tmp/list-skills-output.txt`
- `profile-skills` → `/tmp/profile-skills-output.txt`

### profile-skills `--detail` 모드 예외

`--detail` 플래그는 브라우저를 띄우고 서버를 유지하므로 stdout 리다이렉트 대상이 아니다. 기존 동작 유지: 스크립트 직접 실행 후 URL과 `Ctrl+C` 안내만 확인.

## 트레이드오프

- Read 툴 결과 패널도 `verbose=false` 환경에서 접힐 수 있다. 그러나 사용자가 보는 메인 표시는 Claude가 직접 친 fenced block 이고, Bash의 `+N lines` 노이즈는 사라진다.
- 모든 툴 패널을 완전히 숨기려면 subagent 디스패치 같은 우회가 필요하지만, 효익 대비 복잡도가 커서 채택하지 않는다.
- 임시 파일을 `/tmp` 에 남기는 비용은 무시 가능 (OS 가 정리, 매 실행마다 덮어씀).

## 적용 범위

- `skills/list-skills/SKILL.md` Step 2 ("Display based on `verbose`") 재작성.
- `skills/profile-skills/SKILL.md` "Output Rules" 섹션 재작성.
- 스크립트 (`collect_skills.py`, `report.py`) 는 변경 없음.
