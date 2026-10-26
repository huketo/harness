---
name: full-stop
description: full-send와 같은 작업을 하되 머지하지 않고 사람이 머지할 준비가 된 MR에서 멈추는 작업 모드. 사람이 "/full-stop"이나 "full stop"으로 직접 고를 때와 full-send가 허용 목록에 없는 저장소에서 낮아질 때 쓴다.
disable-model-invocation: true
---

# Full stop

`full-send`와 같은 일을 하되, 사람이 머지할 수 있는 MR에서 멈춘다. 머지하지 않는다.

먼저 `full-send` 스킬 디렉터리의 `scripts/harness-mode set full-stop`을 실행해 모드를 기록한다. 그다음 [full-send](../full-send/SKILL.md)를 읽고 그 절차, 증명 규칙, 리뷰, 감시 단계를 따른다. 사람이 "full stop"을 분명하게 요청하면 따로 "full send"를 요청하지 않아도 그 작업이 허락된다. full-send의 검사 권한도 포함된다. full-send의 머지 권한은 적용되지 않는다. 아래 규칙이 우선한다.

## 머지하지 않기

이 작업의 브랜치에서 커밋, 푸시, rebase, 충돌 해결, `--force-with-lease`를 할 수 있다. 머지, 자동 머지 설정, 머지 큐 진입, 기본 브랜치 푸시, 브랜치 보호 우회, 이런 행동의 위임은 절대 하지 않는다. 머지 가드 훅이 이 모드에서 머지 명령을 막는다.

작업을 시작하기 전에 기존 자동 머지를 끄고 머지 큐에서 빼며, 푸시할 때마다 다시 확인한다(GitLab `glab api -X POST projects/<id>/merge_requests/<iid>/cancel_merge_when_pipeline_succeeds`, GitHub `gh pr merge --disable-auto <n>`). 이 변경을 보고한다. 자동 머지를 막을 수 없으면 진행하기 전에 그 막힘을 보고한다.

## 관문에서 멈추기

full-send의 머지 관문을 준비 상태 점검으로 쓴다. 머지와 최종 보고 단계를 인계로 바꾼다. 증명과 리뷰는 최종 diff를 덮어야 하며, 동작 변경과 의미 있는 충돌 해결은 인계 전에 다시 확인한다. GitLab에서는 `babysit-mr`의 `mr-wait --until ready`가 관문의 기계적인 부분(파이프라인, 승인, 토론, 머지 가능 상태)을 확인한다.

대상 브랜치를 가져오고 실제 MR의 head, 대상, 파이프라인, 리뷰·승인, 머지 가능 상태를 확인한다. MR이 열려 있고 초안이 아니며 사람 없이 머지되도록 설정되어 있지 않은지 확인한다. 다른 사람이 이미 머지했으면 그 사실을 보고한다. 리뷰 봇의 결과는 저장소의 봇 소비 스킬이 있으면 그 스킬의 정상 종료 조건까지 처리한다.

- **머지 준비 완료**: 머지 관문을 통과했다. MR을 열어 두고 머지하지 않는다.
- **승인 대기**: 사람의 승인만 남았다. 그것이 실제 막힘인지 확인한다.
- **막힘**: 무엇이 준비를 막는지, 무엇을 시도했는지, 무엇이 필요한지 설명한다. 질문은 full-send의 "사람에게 묻기"를 따른다.

T3에서는 인계나 질문 전에 `unwatch_pull_request`를 부른다. 마지막에 `scripts/harness-mode clear`를 실행한다. MR 링크, 최종 head, 판정, 증명, 리뷰 결과, 남은 위험을 보고하고, MR이 여전히 열려 있고 머지되지 않았는지 밝힌다.
