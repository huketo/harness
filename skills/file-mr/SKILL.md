---
name: file-mr
description: GitLab MR이나 GitHub PR을 짧게 올릴 때 사용한다. MR·PR을 열거나 만들거나 제출해 달라는 요청, 또는 full-send·full-stop·takeover가 변경을 올리는 단계에 쓴다.
---

# File MR

GitLab이 주 대상이고 GitHub도 같은 절차를 따른다. 원격 호스트로 플랫폼을 고른다: `github.com`이면 `gh`, 그 밖의 GitLab 호스트면 `glab`이다. 두 CLI 모두 사용자의 기존 인증을 쓴다.

## 1. 확인

1. 이 브랜치의 MR·PR이 이미 있는지 확인한다(`glab mr list --source-branch <branch>`, `gh pr list --head <branch>`). 있으면 새로 만들지 않고 그것을 갱신한다.
2. `git fetch origin` 뒤 대상 브랜치(보통 기본 브랜치)와의 diff를 직접 읽고 내용이 목표와 맞는지 확인한다. 관련 없는 변경이 섞였으면 올리기 전에 분리한다.
3. 대상 브랜치의 최신 커밋 위로 rebase가 필요한지 본다. 이미 공유된 브랜치를 rebase하거나 force-push하는 것은 `docs/agents/authority.md`가 정한 별도 결정이다. 이 작업의 새 브랜치이면 `--force-with-lease`로 올릴 수 있다.

## 2. 제목과 본문

제목은 저장소의 관례를 따른다. 최근에 머지된 MR과 git 이력을 보고 맞춘다(conventional commit, 언어). squash 머지에서는 제목이 커밋 메시지가 되므로, 무엇을 바꿨는지보다 왜 중요한지가 드러나게 쓴다.

- 나쁨: `perf(server): negotiate permessage-deflate on the websocket`
- 좋음: `perf(server): cut websocket frame size by 70%+ with gzipping`

본문은 사용자의 원래 요청에 기대어 문제를 쉽게 설명하는 문장으로 시작하고, 그다음 해결을 짧게 적는다. 구현 목록으로 시작하지 않는다. 저장소가 쓰는 본문 언어와 절 구성(검증, 남은 일)을 따른다. 증명 방법은 한 줄로 적는다.

본문의 마지막 줄은 변경을 만든 모델과 하네스다. 변경의 일부를 쓴 하위 agent의 모델도 넣는다. 하네스가 알려 주는 공개 모델 이름을 쓰고, 모델을 알 수 없으면 추측하지 않고 하네스만 적는다. `review-loop`이나 `council`의 결과 줄·절은 이 줄 바로 위에 둔다.

- 영어 본문: `Created with <model> in <harness>.`
- 한국어 본문: `<harness>에서 <model>로 작성했습니다.`

제출 전에 제목, 본문, 인용, 첨부에 비밀값과 사적인 정보가 없는지 확인한다.

## 3. 제출

초안(draft)이 아니라 정식 MR로 연다. 리뷰 봇과 파이프라인이 초안에서는 돌지 않을 수 있기 때문이다.

```sh
glab mr create --source-branch <branch> --target-branch <target> --title "<title>" --description "$(cat <body.md>)" --yes
gh pr create --base <target> --head <branch> --title "<title>" --body-file <body.md>
```

`gh pr create`가 GraphQL 한도로 실패하면 REST로 연다: `gh api repos/<owner>/<repo>/pulls -f title=... -f head=... -f base=... -F body=@<file>`.

T3 스레드이면 만든 직후 `link_pull_request`로 MR·PR URL을 이 스레드에 연결한다. GitLab MR도 같은 도구로 연결된다. 사람이 지켜보기를 요청했으면 `babysit-mr`로 이어 간다.

저장소가 리뷰 봇을 쓰면 첫 리뷰 요청은 그 저장소의 관례를 따른다. 저장소나 하네스에 그 봇의 결과를 소비하는 스킬이 있으면 결과 처리는 그 스킬이 소유한다.

사람의 요청에 필요한 경우가 아니면 후속 댓글을 달지 않는다. 댓글이 필요하면 `leaving-mr-comments` 스킬을 쓴다.
