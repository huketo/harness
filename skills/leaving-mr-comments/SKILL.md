---
name: leaving-mr-comments
description: 사람을 대신해 GitLab MR이나 GitHub PR, 이슈에 댓글·답글·리뷰 의견을 남길 때 항상 사용한다. 봇 지적에 답하거나 해결 처리 전에 이유를 적을 때도 포함한다.
---

# Leaving MR comments

사람을 대신해 에이전트가 쓰는 모든 댓글은 맨 앞에 알림 상자를 둔다. GitHub와 GitLab(17.10 이후)이 같은 문법을 렌더링한다.

```md
> [!NOTE]
> 🤖 **<model> responding on behalf of <user>**

실제 댓글은 여기서 시작한다.
```

- `<model>`은 댓글을 쓴 모델의 확인된 공개 이름이다. 하네스가 모델 이름을 알려 주지 않으면 하네스 이름을 쓴다. 추측하지 않는다.
- `<user>`는 사람의 이름이나 GitLab·GitHub 사용자명이다.
- 한국어 댓글이면 상자 문구도 한국어로 쓴다: `> 🤖 **<user>를 대신해 <model>이 답합니다**`. 상자 밖의 본문 언어와 맞춘다.
- 상자 안에는 이 귀속 표시만 두고 실제 답은 상자 밖에 쓴다. 문맥 줄은 로봇 이모지로 시작한다. 가로줄, Setext 밑줄, 제목, 서명, 두 번째 귀속 표시를 더하지 않는다.

적용 대상: MR·PR의 일반 댓글, 코드 줄 댓글, 리뷰어·봇에 대한 답글, 지적을 해결 처리하거나 기각하기 전에 남기는 설명. MR 본문, 커밋 메시지, 사람이 귀속 표시 없이 그대로 올려 달라고 한 글에는 붙이지 않는다.

본문은 직접적으로 쓴다.

- 결론을 먼저 쓴다.
- 관련 코드, 동작, 검사, 재현을 인용한다(`file:line`, 커밋 SHA, 파이프라인 링크).
- 군더더기, 형식적인 감사, 진행 상황 서술을 넣지 않는다.
- 확인한 사실과 판단을 구분한다.

올리기 전에 인용과 첨부를 포함한 전체 댓글에 비밀값과 사적인 정보가 없는지 확인하고, 최종 Markdown을 미리 보고 인용 블록과 빈 줄이 의도대로 렌더링되는지 확인한다.

- GitLab: 토론 답글은 `glab api -X POST projects/<id>/merge_requests/<iid>/discussions/<discussion_id>/notes -F body=@<file>`, 새 댓글은 `glab api -X POST projects/<id>/merge_requests/<iid>/notes -F body=@<file>`(실험 단계인 `glab mr note` 대신 REST를 쓴다), 해결 처리는 `glab api -X PUT projects/<id>/merge_requests/<iid>/discussions/<discussion_id> -f resolved=true`.
- GitHub: `gh pr comment <n> --body-file <file>`, 줄 댓글 답글은 `gh api repos/<o>/<r>/pulls/<n>/comments/<id>/replies -F body=@<file>`.

올린 뒤 서버가 돌려준 댓글이나 note의 URL·ID를 확인한다. 토론은 답글이 성공적으로 올라간 뒤에만 해결 처리한다. 리뷰 봇의 지적에 답하거나 해결 처리할 때 그 봇을 소비하는 스킬이 있으면 그 규칙을 함께 따른다.
