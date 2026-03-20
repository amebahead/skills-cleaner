# Skills Cleaner

설치된 Claude Code 스킬들의 유사성을 비교하고, 중복/겹치는 스킬을 식별하여 대화형으로 정리할 수 있게 안내하는 플러그인.

## 설치

```bash
claude plugin marketplace add amebahead/skills-cleaner
claude plugin install skills-cleaner
```

또는 Claude Code 내에서:

```
/plugin marketplace add amebahead/skills-cleaner
/plugin install skills-cleaner
```

## 사용법

Claude Code에서 아래와 같이 요청하면 자동으로 스킬이 트리거됩니다:

- "스킬 정리해줘"
- "중복 스킬 확인해줘"
- "설치된 스킬들 비교해줘"

## 동작 방식

4단계 파이프라인으로 동작합니다:

```
수집 → 병렬 비교 → 리포트 → 대화형 제거 안내
```

### Stage 1: 스킬 수집

개인 스킬(`~/.claude/skills/`)과 플러그인 스킬(`~/.claude/plugins/cache/`)에서 SKILL.md 파일을 수집합니다.

### Stage 2: 병렬 비교

서브에이전트를 활용해 스킬 쌍을 병렬로 비교합니다. 4가지 차원(목적, 트리거, 프로세스, 출력)에서 유사도를 분석합니다.

### Stage 3: 리포트

유사도 70% 이상인 쌍만 내림차순으로 정렬하여 보여줍니다.

```
#1  executing-plans ↔ subagent-driven-development
    Similarity: ██████████████████░░ 85%
    Source: plugin ↔ plugin
```

| 등급 | 유사도 | 의미 |
|------|--------|------|
| 🔴 | 90%+ | 제거 후보 |
| 🟡 | 70-89% | 검토 필요 |
| 🟢 | <70% | 고유 (리포트 제외) |

### Stage 4: 대화형 제거 안내

유사 쌍을 하나씩 보여주며 사용자에게 제거/유지를 묻습니다. 최종 삭제 전 확인 게이트를 거칩니다.

- **개인 스킬**: 디렉토리 직접 삭제
- **플러그인 스킬**: 직접 삭제하지 않고 비활성화/제거 방법 안내

## 프로젝트 구조

```
skills-cleaner/
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json
├── skills/
│   └── skills-cleaner/
│       └── SKILL.md
└── docs/
    └── superpowers/specs/
        └── 2026-03-19-skills-cleaner-design.md
```

## 라이선스

MIT
