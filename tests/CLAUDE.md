# tests 모듈

## Role

작업 도구(하네스)가 실제로 동작하는지 확인하는 시험입니다. 훅, `.claude/settings.json`, 스킬과 에이전트의 형식, 문서의 구조와 포인터를 봅니다. 앱의 시험은 여기에 없습니다. BFF 시험은 `app/bff/test_bff.py`, 화면 시험은 `app/web/*.test.mjs`입니다.

## Key Files

| 파일 | 내용 |
|---|---|
| `run-all.sh` | 실행기. `test-*.sh`를 찾아 source로 불러 실행하고 통과, 실패, 건너뜀을 셈 |
| `hooks/test-hooks.sh` | 훅의 존재와 권한, 설정 등록, 훅의 실제 동작(문서 알림, 비밀 값 차단, 세션 맥락, 커밋 메시지 훅) |
| `hooks/test-secret-patterns.sh` | 비밀 값과 환경 식별 값 패턴의 검출과 오검출. 실제 검사기를 실행하고, 식별 값은 가리기 도구를 거치면 통과하는지도 확인 |
| `structure/test-project-structure.sh` | CLAUDE.md의 구역과 `@AGENT.md`, 모듈 문서, 스킬과 에이전트의 frontmatter, 두 언어 문서의 구조, README의 아키텍처 그림(파일이 있고 git이 추적하는지, 영어 구역은 영어판이고 한국어 구역은 한국어판인지), 참조 문서의 경로 |
| `fixtures/secret-samples.txt` | 검출해야 하는 표본. 접두어와 본문을 나눠 저장하고 실행할 때 합침 |
| `fixtures/identifier-samples.txt` | 막아야 하는 환경 식별 값의 표본(지어낸 값) |
| `fixtures/false-positives.txt` | 검출하면 안 되는 표본 |

## Rules

- 실행: `bash tests/run-all.sh`. 이름으로 고르려면 `bash tests/run-all.sh hooks`, `bash tests/run-all.sh structure`
- 시험 파일은 실행기와 같은 셸에서 돕니다. `TOTAL`, `PASSED`, `FAILED`, `SKIPPED`, `FAILURES` 같은 실행기의 변수 이름을 쓰지 않습니다. 덮어쓰면 실행기가 "카운터가 맞지 않거나 실행한 시험이 없습니다"로 실패합니다
- 실행기는 `set -e`를 쓰지 않습니다. 아무것도 찾지 못한 `grep`이 실행을 끊으면 안 되기 때문입니다. 모든 확인은 `pass`, `fail`, `skip`으로 보고합니다
- 완전한 비밀 값 문자열을 저장소에 두지 않습니다. 표본은 접두어와 본문으로 나눕니다
- 임시 파일과 임시 git 저장소는 `$TEST_TMP` 아래에 만듭니다
- 훅이나 구조를 바꾸면 시험도 함께 바꿉니다. 새 시험은 일부러 깨뜨렸을 때 실패하는지 확인합니다(`|| true`를 붙여 보거나 경로를 틀리게 해 봅니다)
- 이 시험은 AWS와 클러스터를 부르지 않습니다
