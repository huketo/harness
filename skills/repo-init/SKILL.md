---
name: repo-init
description: 하네스 스킬이 저장소마다 읽는 문서(AGENTS.md 라우터, docs/agents/, 이슈 트래커 문서, 용어집, ADR)를 새 저장소나 문서가 부족한 저장소에 만든다.
disable-model-invocation: true
---

# Repo init

하네스 스킬들이 저장소마다 기대하는 문서를 한 번에 만든다. 결정론적 스크립트가 아니라 프롬프트로 진행하는 절차다. 저장소를 탐색하고, 발견 사항을 보여 주고, 섹션마다 확인을 받고, 초안을 확인받은 뒤에 쓴다.

| 대상 파일 | 템플릿 | 읽는 쪽 |
| --- | --- | --- |
| `AGENTS.md` | [templates/AGENTS.md](templates/AGENTS.md) | 저장소에서 일하는 모든 에이전트(라우터) |
| `CLAUDE.md` | [templates/CLAUDE.md](templates/CLAUDE.md) | Claude Code(`@AGENTS.md`로 라우터를 읽는다) |
| `docs/agents/workflow.md` | [templates/docs/agents/workflow.md](templates/docs/agents/workflow.md) | 라우터를 따르는 에이전트 |
| `docs/agents/authority.md` | [templates/docs/agents/authority.md](templates/docs/agents/authority.md) | `file-mr`, `full-send`, `full-stop` |
| `docs/agents/writing.md` | [templates/docs/agents/writing.md](templates/docs/agents/writing.md) | 문서를 고치는 에이전트 |
| `docs/agents/testing.md` | [templates/docs/agents/testing.md](templates/docs/agents/testing.md) | `t3-orchestrate` 브리프(테스트 실행 방법), 검사 명령을 고르는 에이전트 |
| `docs/agents/hitl.md` | [templates/docs/agents/hitl.md](templates/docs/agents/hitl.md) | `full-send`, `council`, `t3-terminal`, `t3-orchestrate` |
| `docs/agents/issue-tracker.md` | [GitHub](templates/docs/agents/issue-tracker-github.md), [GitLab](templates/docs/agents/issue-tracker-gitlab.md), [로컬](templates/docs/agents/issue-tracker-local.md) 중 하나 | `code-review`, `issue-doctor` |
| `GLOSSARY.md` 또는 `GLOSSARY-MAP.md` | [templates/GLOSSARY.md](templates/GLOSSARY.md), [templates/GLOSSARY-MAP.md](templates/GLOSSARY-MAP.md) | `domain-modeling`, `improve-codebase-architecture`, `codebase-design`, `diagnosing-bugs`, `wait-what` |
| `docs/adr/README.md` | [templates/docs/adr/README.md](templates/docs/adr/README.md) | `domain-modeling`, `improve-codebase-architecture`, `diagnosing-bugs` |

이 스킬은 저장소 작업 디렉터리 안의 파일만 쓴다. 원격 추가, 푸시, 라벨과 이슈 생성, 저장소 설정 변경은 범위 밖이므로, 필요하면 사람이 직접 실행할 명령을 완료 보고에 적어 안내만 한다. 커밋은 사람이 요청할 때만 한다.

질문은 하네스의 질문 도구로 한다. 대상 저장소에 `docs/agents/hitl.md`가 이미 있으면 그 규칙을 따른다. 위임된 자식이나 예약 실행처럼 사람이 없는 실행이면 질문하지 않는다. 그때는 2단계의 발견 사항과 섹션별 권장 답을 결과로 남기고, 파일을 쓰지 않은 채 끝낸다.

## 1. 탐색

저장소 루트는 `git rev-parse --show-toplevel`로 정한다. git 저장소가 아니면 현재 디렉터리를 루트로 삼고 그 사실을 발견 사항에 적는다. 있는 것을 읽고, 없는 것을 가정하지 않는다.

1. **원격**: `git remote -v`. 호스트가 `github.com`이면 GitHub이고, `gitlab.com`이거나 호스트 이름에 `gitlab`이 들어 있으면 GitLab이다. 원격의 경로(`owner/name`, GitLab은 그룹을 포함한 전체 경로)와 호스트를 적는다. `.scratch/`가 있으면 로컬 마크다운 트래커를 이미 쓰고 있다는 신호로 적는다.
2. **에이전트 지시 파일**: 루트의 `AGENTS.md`와 `CLAUDE.md`가 각각 없는지, `@AGENTS.md` 한 줄만 있는지, 내용이 있는지 적는다. 내용이 있으면 제목 목록과 `docs/agents/`를 가리키는 줄이 있는지 적는다.
3. **`docs/agents/`**: 여섯 대상 파일(`workflow.md`, `authority.md`, `writing.md`, `testing.md`, `hitl.md`, `issue-tracker.md`)과 그 밖의 파일이 있는지 보고, 있는 파일은 제목 목록을 적는다.
4. **용어집**: 루트의 `GLOSSARY.md`·`GLOSSARY-MAP.md`와 예전 이름 `CONTEXT.md`·`CONTEXT-MAP.md`를 찾는다. 맵이 있으면 맵이 가리키는 컨텍스트별 파일도 확인한다.
5. **ADR**: `docs/adr/`와 컨텍스트별 `*/docs/adr/`를 찾고 기록 수를 적는다. 다른 위치에 결정 기록(`docs/decisions/` 등)이 있으면 그 경로를 적고 옮기지 않는다.
6. **표준 문서**: 루트, `docs/`, `.github/`에서 `CONTRIBUTING.md`와 `CODING_STANDARDS.md`를 찾는다.
7. **검사·빌드 명령의 근거**: 명령을 정의하거나 실행하는 파일을 읽고, 명령마다 목적(test, lint, typecheck, build)과 `path:line`을 적는다.
   - `package.json`의 `scripts`. 실행기는 `packageManager` 필드와 잠금 파일(`pnpm-lock.yaml`, `yarn.lock`, `bun.lock`·`bun.lockb`, `package-lock.json`)로 정한다.
   - `Makefile`·`justfile`의 타깃, `pyproject.toml`의 작업 설정(`[tool.poe.tasks]`, `[tool.hatch.envs.*.scripts]`, `[tool.pytest.ini_options]`), `tox.ini`, `noxfile.py`.
   - CI 설정: `.github/workflows/*.yml`, `.gitlab-ci.yml`, 그 밖의 CI 파일이 실행하는 명령.
   - `Cargo.toml`이나 `go.mod`만 있고 그것을 실행하는 스크립트나 CI 단계가 없으면, 도구의 기본 명령(`cargo test`, `go test ./...`)은 근거가 아니라 후보로 적는다.
   - 배포, 릴리스, 게시, 마이그레이션처럼 실제 효과가 있는 명령은 따로 적는다.
8. **모노레포 신호**: `pnpm-workspace.yaml`, `package.json`의 `workspaces`, `lerna.json`, `nx.json`, `turbo.json`, `go.work`, `Cargo.toml`의 `[workspace]`, 각자 매니페스트와 소스를 가진 `packages/*`·`apps/*`.
9. **문서의 주 언어**: `README*`, `docs/`, `CONTRIBUTING.md`의 산문(코드 블록 제외)에서 가장 많이 쓴 언어를 적는다. `README.md`와 `README.<lang>.md`가 함께 있으면 `README.md`의 언어가 주 언어다. 산문이 없으면 판단 불가로 적는다.
10. **이름, 요약, 최상위 디렉터리**: README 제목과 첫 문단, 매니페스트의 `name`·`description`, 추적 중인 최상위 디렉터리(`git ls-files | cut -d/ -f1 | sort -u`)와 README나 매니페스트로 확인한 각 디렉터리의 역할을 적는다.

완료 기준: 열 항목마다 근거 경로를 붙인 값, "없음", "판단 불가" 가운데 하나가 채워져 있다.

## 2. 발견 사항 제시

탐색 결과를 항목별 표로 보여 준다. 그 아래에 대상 파일마다 할 일을 하나씩 적는다: 새로 만듦, 빠진 절을 더함, `git mv`로 이름을 바꿈, 그대로 둠. 이미 있는 파일은 덮어쓰지 않는다. 빠진 절은 그 파일 안의 알맞은 위치에 더하자고 제안한다. 다른 표현으로라도 같은 주제를 다루는 절이 이미 있으면, 그 절은 빠진 것이 아니다.

## 3. 섹션별 확인

섹션을 순서대로 하나씩 묻고, 답을 받은 뒤 다음 섹션으로 간다. 권장 답을 첫 선택지로 두어 사람이 한마디로 받아들일 수 있게 한다. 선택이 실제로 갈릴 때만 한 줄 설명을 붙이고, 탐색으로 이미 정해진 섹션은 묻지 않는다.

**A. 문서 언어.** 탐색에서 주 언어가 정해졌으면 묻지 않고 그 언어와 근거를 발견 사항에 적는다. 판단 불가이면 묻고, 권장 답은 영어로 둔다. 템플릿 원문이 영어여서 옮기는 과정에서 뜻이 바뀌지 않기 때문이다. `hitl.md`의 질문 언어는 이 세션에서 사람이 쓰는 언어로 정하며 따로 묻지 않는다.

**B. 이슈 트래커.** 원격이 GitHub이면 GitHub(`gh`)를, GitLab이면 GitLab(`glab`)을 권장 답으로 둔다. 원격이 없고 `.scratch/`가 있으면 로컬 마크다운을 권장한다. 그 밖의 경우에는 네 선택지를 보여 준다.

- GitHub: 저장소의 GitHub Issues를 `gh`로 쓴다.
- GitLab: 저장소의 GitLab Issues를 `glab`으로 쓴다.
- 로컬 마크다운: `.scratch/<feature>/` 아래의 파일로 관리한다. 혼자 하는 프로젝트나 원격이 없는 저장소에 맞다.
- 그 밖(Jira, Linear 등): 사람이 작업 방식을 한 문단으로 설명하면, 그 설명을 `docs/agents/issue-tracker.md`에 그대로 적는다.

GitHub나 GitLab을 골랐는데 그 호스트를 가리키는 원격이 없으면, 저장소 경로(GitLab이면 호스트도)를 물어서 문서에 적는다. 원격 추가 명령은 완료 보고에서 안내만 한다.

**C. 에이전트 지시 파일.** 탐색 결과에 따라 아래와 같이 처리하며, 마지막 경우에만 묻는다.

- 둘 다 없음: 두 템플릿으로 새로 만든다.
- `CLAUDE.md`에만 내용이 있음: `AGENTS.md`를 새로 만들고, `CLAUDE.md`의 첫 줄에 `@AGENTS.md`를 더한다. 기존 내용은 그대로 둔다.
- `AGENTS.md`에만 내용이 있음: `AGENTS.md`에 빠진 절을 더하고, `CLAUDE.md`를 `@AGENTS.md` 한 줄로 새로 만든다.
- `CLAUDE.md`가 이미 `@AGENTS.md` 한 줄뿐임: `CLAUDE.md`는 그대로 두고 `AGENTS.md`만 다룬다.
- 둘 다 내용이 있음: 어느 쪽을 정본으로 둘지 묻는다. 권장 답은 `AGENTS.md`다. Codex 같은 다른 하네스도 이 파일을 읽고, Claude Code는 `@AGENTS.md`로 읽기 때문이다. 정본에는 빠진 절을 더하고, 다른 쪽에는 정본을 가리키는 한 줄만 더한다(`CLAUDE.md`에는 `@AGENTS.md`, `AGENTS.md`에는 `Read CLAUDE.md first; it holds this repository's agent rules.`). 두 파일의 기존 내용은 옮기거나 지우지 않고, 중복이나 충돌을 발견했으면 완료 보고에 적는다.

**D. 도메인 문서 배치.** 용어집 배치가 이미 있으면(루트 `GLOSSARY.md`나 `GLOSSARY-MAP.md`, 또는 예전 이름의 같은 파일) 모노레포 신호와 관계없이 그 배치를 따르고 묻지 않는다. 용어집이 없을 때 모노레포 신호가 없으면 묻지 않고 단일 컨텍스트(루트 `GLOSSARY.md`와 `docs/adr/`)로 정한다. 신호가 있으면 다중 컨텍스트(루트 `GLOSSARY-MAP.md`와 컨텍스트별 `GLOSSARY.md`)를 권장 답으로 두고, 도메인 코드를 가진 패키지를 컨텍스트 후보로 보여 준다. 공유 설정이나 도구만 담은 패키지는 후보에서 뺀다. 사람이 단일 컨텍스트를 고르면 그대로 따른다.

예전 이름의 파일이 있으면 같은 섹션에서 처리한다.

- `CONTEXT.md`·`CONTEXT-MAP.md`만 있음: `git mv CONTEXT.md GLOSSARY.md`(맵이면 `git mv CONTEXT-MAP.md GLOSSARY-MAP.md`와 맵이 가리키는 각 `CONTEXT.md`의 이동)를 권장 답으로 제안한다. 새 이름의 파일을 그 옆에 따로 만들지 않는다. 사람이 이동을 거절하면 예전 이름의 파일을 그대로 두고, 라우터의 `GLOSSARY_ENTRY`에는 그 파일의 경로를 적는다.
- 새 이름과 예전 이름이 함께 있음: 새 이름의 파일을 정본으로 읽고, 예전 이름의 파일은 중복으로 완료 보고에 적는다. 옮기거나 지우지 않는다.
- 새 이름의 용어집이 이미 있음: 그대로 둔다.

완료 기준: 네 섹션마다 사람의 답이나 탐색 근거로 정한 값이 하나씩 있다.

## 4. 초안 확인

대상 파일마다 초안을 만든다. 문서 언어가 영어가 아니면 템플릿을 그 언어로 옮긴다. 명령, 경로, 파일 이름, 식별자는 옮기지 않는다. 이슈 트래커는 고른 템플릿 하나로 `docs/agents/issue-tracker.md`를 만들고, "그 밖"을 골랐으면 사람의 설명으로 처음부터 쓴다.

템플릿의 `{{이름}}` 자리는 아래 근거로만 채운다. 근거가 없을 때의 처리도 표를 따르며, 값을 지어내지 않는다.

| 자리 | 채우는 값 | 근거가 없을 때 |
| --- | --- | --- |
| `PROJECT_NAME` | README 제목, 매니페스트 `name`, 원격 경로의 마지막 부분, 디렉터리 이름 순으로 처음 찾은 값 | 디렉터리 이름 |
| `PROJECT_SUMMARY` | README 첫 문단이나 매니페스트 `description`에서 저장소가 무엇인지 말하는 한 문장 | 자리를 지운다 |
| `OWNERSHIP_MAP` | 최상위 디렉터리마다 `` - `dir/` — role. `` 한 줄. 역할은 확인한 것만 적는다 | 아직 소스 디렉터리가 없으며 디렉터리가 생길 때마다 한 줄씩 더한다는 문장 |
| `STANDARDS_POINTERS` | 있는 `CONTRIBUTING.md`·`CODING_STANDARDS.md`마다 라우터 목록 형식의 한 줄 | 줄을 지운다 |
| `GLOSSARY_ENTRY` | `GLOSSARY.md` 또는 `GLOSSARY-MAP.md`(D의 결정) | 없음 |
| `PROJECT_DECISIONS` | 탐색에서 찾은 실제 효과가 있는 명령마다 `` - Running `<command>` (`<path:line>`), which <effect>. `` | 줄을 지운다 |
| `DOCUMENT_MAP` | 있는 문서와 이번에 만드는 문서마다 `` - `path` — what it owns. `` | 없음(이번에 만드는 문서가 항상 있다) |
| `DOC_LANGUAGE_RULE` | 주 문서 언어를 정하는 문장. 번역본 README가 있으면 원본과 함께 고친다는 문장을 더한다 | 없음(A에서 정한다) |
| `COMMAND_ROWS` | 찾은 명령마다 `` \| purpose \| `command` \| `path:line` \| `` 한 행 | 표 전체를 정의된 검사 명령이 아직 없다는 한 문장으로 바꾼다 |
| `MISSING_COMMANDS` | 근거를 찾지 못한 목적마다 찾아본 파일과 그 결과, 도구 기본 명령 후보. 같은 이유로 찾지 못한 목적은 한 줄로 묶는다 | 모두 찾았으면 `- None.` |
| `LIVE_EFFECT_COMMANDS` | 실제 효과가 있는 명령마다 명령, `path:line`, 효과 | `None found.` |
| `PERSON_LANGUAGE` | 이 세션에서 사람이 쓰는 언어 | 없음 |
| `REPO_SLUG` | 원격 경로(GitLab은 그룹 포함) | B에서 사람이 준 경로. 그것도 없으면 `` the repository `origin` points to `` |
| `GITLAB_HOST` | 원격 호스트, 원격이 없으면 B에서 사람이 준 호스트 | `gitlab.com` |
| `CONTEXT_NAME` | 단일 컨텍스트이면 `PROJECT_NAME`, 다중이면 컨텍스트 이름 | 없음 |
| `CONTEXT_DESCRIPTION` | 그 컨텍스트가 무엇이고 왜 있는지 말하는 한두 문장(README, 매니페스트) | 자리를 지운다 |
| `CONTEXT_LIST` | 확정한 컨텍스트마다 `` - [Name](./path/GLOSSARY.md) — one-line purpose `` | 없음(다중 컨텍스트일 때만 쓴다) |

`testing.md`에는 탐색에서 실제로 찾은 명령만 적는다. 근거를 찾지 못한 목적은 `MISSING_COMMANDS`에 비워 둔 자리로 남기고, 찾아본 파일과 찾지 못한 이유를 적는다.

초안을 보여 준다. 새 파일은 전문을, 이미 있는 파일은 더할 절과 그 절이 들어갈 위치(어느 제목 뒤인지)를 보여 준다. 사람이 고칠 기회를 준 뒤 "이대로 쓴다"를 권장 답으로 두고 승인을 받는다.

완료 기준: 모든 초안에 `{{`가 하나도 남아 있지 않고, 사람이 초안을 승인했다.

## 5. 쓰기

1. 새 파일은 쓰기 직전에 `test -e`로 없음을 다시 확인한 뒤 만든다. 그사이에 생겼으면 그 파일은 빠진 절을 더하는 경우로 돌려 다시 확인받는다.
2. 이미 있는 파일에는 승인된 절만 승인된 위치에 더하고 기존 문장은 바꾸지 않는다.
3. 승인된 이름 변경은 `git mv`로 한다(추적되지 않는 파일이면 `mv`). 옮긴 뒤 맵과 문서 안의 예전 경로를 새 경로로 고친다.
4. 다중 컨텍스트이면 `GLOSSARY-MAP.md`와 확정한 컨텍스트마다 `GLOSSARY.md`를 만든다. 이미 용어집이 있는 컨텍스트는 건너뛴다.
5. `docs/adr/README.md`는 `docs/adr/`에 README가 없을 때만 만든다. 기존 ADR은 건드리지 않는다.

완료 기준: 아래 세 가지가 모두 확인된다.

- `git status --short`에 승인한 파일만 나타난다.
- 쓴 파일에서 `grep -n '{{'`의 결과가 비어 있다.
- 쓴 파일의 상대 링크가 모두 실제 파일이나 디렉터리를 가리킨다.

## 6. 완료 보고

아래 내용을 보고한다.

- 만든 파일, 절을 더한 파일(더한 절의 제목), 이름을 바꾼 파일, 그대로 둔 파일과 그 이유.
- 이제 어떤 스킬이 어느 파일을 읽는지. 위의 대상 파일 표를 기준으로 적는다.
- 비워 둔 자리: `testing.md`의 정의되지 않은 명령, 표준 문서가 없어서 `code-review`가 기본 코드 냄새 목록(smell baseline)만 쓴다는 사실, 아직 용어가 없는 용어집(`/domain-modeling`으로 채운다).
- 사람이 직접 할 수 있는 일과 그 명령: 원격 추가(`git remote add origin <url>`), CLI 인증 확인(`gh auth status`, `glab auth status`), 커밋. 이 스킬은 이 명령들을 실행하지 않는다.
- `docs/agents/*.md`는 사람이 직접 고쳐도 된다는 사실. 이 스킬을 다시 실행하면 빠진 절만 제안한다는 사실.
