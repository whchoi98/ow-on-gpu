# Changelog

[![English](https://img.shields.io/badge/lang-English-blue.svg)](#english)
[![한국어](https://img.shields.io/badge/lang-한국어-red.svg)](#한국어)

---

<a id="english"></a>

# English

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Keep the descriptions of all eight steps below the map in the API call view instead of showing only the current step

## [1.0.0] - 2026-11-17

### Added

- Add the EKS cluster, the Karpenter NodePools and the S3 model bucket for serving on g6e.4xlarge nodes
- Add a Job that loads model weights from Hugging Face into S3 so serving pods read only from S3
- Add vLLM v0.33.0 deployments for Gemma 4 31B and Qwen3.8-27B with compile caches restored from S3
- Add the inference gateway with one InferencePool and endpoint picker per model
- Add the Strands Decider 2B service behind the gateway path `/decide`
- Add the sleep schedule and the wake API for Qwen
- Add the BFF with Cognito login, routing rules, an order lookup tool and SSE relay
- Add the check page with request, chat, benchmark, routing, status and architecture views
- Add metrics collection to Amazon Managed Service for Prometheus and a serving dashboard
- Add measurement scripts for cold start, sleep recovery, TTFT by segment, throughput under the SLO and priority
- Add a web search tool that calls Amazon Bedrock AgentCore Web Search and numbers its sources
- Add the API call view, the build steps view and a Korean and English switch to the check page
- Add English texts in the BFF, selected by the `x-lang` request header
- Add the `fallback` value of the `x-bff-search` response header for requests sent with the default handling
- Add `scripts/mask-identifiers.py` and a pre-commit check that keep environment identifiers such as account IDs, ARNs and CloudFront addresses out of committed files

### Changed

- Move the BFF from ECS Fargate to EKS pods on a Graviton NodePool behind an ALB created by the AWS Load Balancer Controller
- Run the Qwen node On-Demand instead of Spot
- Opt the BFF pods out of the automatic instrumentation added by a cluster webhook
- Track placeholder-only `*.example` files instead of the five files that hold environment-specific values
- Write the streaming unit as "Chunk" instead of a Korean word in the Korean texts of the check page, the infographic and the documents
- Stop treating a request as sensitive when only the Decider's model choice is below the confidence threshold, so web search is attached to it

### Removed

- Remove the ECS Fargate service, the Terraform-managed ALB and the NLB of the wake API

[Unreleased]: https://github.com/whchoi98/ow-on-gpu/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/whchoi98/ow-on-gpu/releases/tag/v1.0.0

---

<a id="korean"></a>

# 한국어

이 프로젝트의 모든 주요 변경 사항은 이 파일에 기록됩니다.
이 문서는 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)를 기반으로 하며,
[Semantic Versioning](https://semver.org/spec/v2.0.0.html)을 따릅니다.

## [Unreleased]

### Changed

- API 호출 보기의 지도 아래에 지금 단계 하나가 아닌 여덟 단계의 설명을 모두 두도록 변경

## [1.0.0] - 2026-11-17

### Added

- g6e.4xlarge 노드에서 서빙하기 위한 EKS 클러스터, Karpenter NodePool, S3 모델 버킷 추가
- 서빙 파드가 S3에서만 읽도록 Hugging Face의 모델 가중치를 S3에 적재하는 Job 추가
- S3에서 compile 캐시를 복원하는 Gemma 4 31B와 Qwen3.8-27B의 vLLM v0.33.0 Deployment 추가
- 모델마다 InferencePool과 엔드포인트 선택기를 둔 추론 게이트웨이 추가
- 게이트웨이 경로 `/decide` 뒤의 Strands Decider 2B 서비스 추가
- Qwen의 sleep 일정과 깨우기 API 추가
- Cognito 로그인, 경로 결정 규칙, 주문 조회 도구, SSE 전달을 갖춘 BFF 추가
- 요청, 대화, 성능 평가, 경로 판단, 상태, 구조 보기가 있는 확인용 페이지 추가
- Amazon Managed Service for Prometheus로의 지표 수집과 서빙 대시보드 추가
- 콜드 스타트, sleep 복귀, 구간별 TTFT, SLO 하 처리량, 우선순위 측정 스크립트 추가
- Amazon Bedrock AgentCore Web Search를 부르고 출처에 번호를 붙이는 웹 검색 도구 추가
- 확인용 페이지에 API 호출 보기, 구축 과정 보기, 한영 전환 추가
- 요청 헤더 `x-lang`으로 고르는 BFF의 영어 문구 추가
- 기본값으로 보낸 요청을 알리는 응답 헤더 `x-bff-search`의 `fallback` 값 추가
- 계정 ID, ARN, CloudFront 주소 같은 환경 식별 값이 커밋에 들어가지 않도록 `scripts/mask-identifiers.py`와 커밋 전 검사 추가

### Changed

- BFF를 ECS Fargate에서 AWS Load Balancer Controller가 만든 ALB 뒤의 Graviton NodePool EKS 파드로 이전
- Qwen 노드를 Spot에서 On-Demand로 변경
- 클러스터 웹훅이 붙이는 자동 계측을 BFF 파드가 받지 않도록 변경
- 환경별 값이 든 파일 다섯 개 대신 자리 표시만 든 `*.example` 파일을 추적하도록 변경
- 확인용 페이지, 인포그래픽, 문서의 한국어 문구에서 스트리밍 전송 단위를 "조각" 대신 "Chunk"로 표기하도록 변경
- Decider의 모델 선택 신뢰도만 기준보다 낮은 요청은 민감 정보 요청으로 다루지 않고 웹 검색을 붙이도록 변경

### Removed

- ECS Fargate 서비스, Terraform이 만든 ALB, 깨우기 API의 NLB 제거

[Unreleased]: https://github.com/whchoi98/ow-on-gpu/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/whchoi98/ow-on-gpu/releases/tag/v1.0.0
