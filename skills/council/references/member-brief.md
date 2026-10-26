# 위원 브리프 양식

위원은 대화 기록, 하네스 규칙, 저장소의 `AGENTS.md`를 받는다고 가정하지 않는다. 특히 T3의 Antigravity는 별도 `GEMINI_HOME`에서 실행되어 사용자 규칙과 플러그인을 읽지 않는다. 그래서 필요한 규칙을 아래 "Rules" 절에 모두 적고, 모든 경로를 절대 경로로 준다. 세 위원에게 같은 본문을 보낸다. Codex 위원에게는 이 본문을 상태 디렉터리에 저장하고 `--brief "Read <절대 경로> and carry it out exactly."`로 넘긴다.

코드 대상이면 "Criteria"에 `review-loop`의 `references/review.md`에 있는 A~D절과 심각도 정의를 그대로 붙인다. 설계·계획 대상이면 같은 심각도 정의와 함께 "의도한 결과를 내는가, 더 단순한 대안이 있는가, 되돌리기 비용과 실패 방식은 무엇인가, 근거가 확인 가능한가"를 붙인다.

```markdown
# Council <slug> round <n>

You are one member of a review council. Other members review the same material independently. Your job is to make the work better within its stated intent, not to vote.

## Rules
- Review only. Do not edit files, create files in the repository, commit, push, comment on MRs or PRs, change settings, or start subagents. Reading files and running read-only commands (git log/diff/show, grep, tests that write only to ignored paths) is allowed.
- Do not ask a person. Put questions in your reply.
- Ground every finding: cite file:line, a command and its output, or an exact primary-source URL. Mark anything you could not verify as unverified.
- Hold the work to the smallest version that meets the intent. A request for features, defenses, or compatibility the intent does not need is scope creep: list it as a nit.
- All paths below are absolute. The working directory may not be the repository.

## Material
- Repository: <abs path>   Base: <sha>   Head: <sha or "working tree, see diff">
- Diff or document: <abs path(s)>; commits: <abs path>
- Intent: <1-2 sentences>   Out of scope: <list>
- Acceptance criteria or decision to make: <verbatim>
- Checks already run: <command → result>
(round 2+) - Ledger: <rows with fixed:/disagree:/declined: and evidence>
(round 2+) - Changed since last round: <abs path>. Review open ids and changed parts only; mark each old id `resolved` or `still open: <reason>`.

## Criteria
<paste the criteria for this material>

## Reply format (exactly)
SCORE: <0-10>/10
VERDICT: SATISFIED or CHANGES
C1 [blocker|should|nit] <file:line or section> <claim>. Fix: <suggestion>
C2 ...
(stable ids across rounds; SATISFIED requires no open blocker or should)
COUNCIL_DONE
```

`SCORE`는 지금 상태를 의도 대비 10점 만점으로 매긴 값이다. 위원이 양식을 지키지 않으면 그 회차는 `no score`이며 이 스레드가 점수를 대신 매기지 않는다.
