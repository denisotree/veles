# 프로젝트 백업 및 공유 방법

> 🌐 **언어:** [English](../../en/how-to/backup-and-share.md) · [简体中文](../../zh-CN/how-to/backup-and-share.md) · [繁體中文](../../zh-TW/how-to/backup-and-share.md) · [日本語](../../ja/how-to/backup-and-share.md) · **한국어** · [Español](../../es/how-to/backup-and-share.md) · [Français](../../fr/how-to/backup-and-share.md) · [Italiano](../../it/how-to/backup-and-share.md) · [Português (BR)](../../pt-BR/how-to/backup-and-share.md) · [Português (PT)](../../pt-PT/how-to/backup-and-share.md) · [Русский](../../ru/how-to/backup-and-share.md) · [العربية](../../ar/how-to/backup-and-share.md) · [हिन्दी](../../hi/how-to/backup-and-share.md) · [বাংলা](../../bn/how-to/backup-and-share.md) · [Tiếng Việt](../../vi/how-to/backup-and-share.md)

Veles 프로젝트는 이식 가능합니다. 백업이나 마이그레이션을 위해 프로젝트 전체를
단일 `.tar.gz` 번들로 내보내거나, 데이터 유출 없이 공유할 수 있는 정제된 템플릿으로
내보낼 수 있습니다.

## 전체 백업

런타임 임시 파일(잠금, 예산 상태)을 제외한 프로젝트 전체(`.veles/` + `AGENTS.md`)를
압축합니다:

```bash
veles export full ./my-project-backup.tar.gz
```

어디서든 복원할 수 있습니다:

```bash
veles import ./my-project-backup.tar.gz                # 현재 디렉터리에 복원
veles import ./my-project-backup.tar.gz --into ./restored
veles import ./my-project-backup.tar.gz --force        # 기존 .veles/ 덮어쓰기
```

전체 번들에는 `memory.db`(세션, 인사이트)가 포함되므로 개인 데이터처럼 취급하세요.

## 공유 가능한 템플릿

재사용 가능한 스캐폴딩만 압축합니다 — 스키마, 스킬, 모듈, 세션이 없는 위키 페이지.
`memory.db`, `sources/`, `sessions/`, 신뢰 권한을 **제거**하고 텍스트의 개인정보를
제거합니다:

```bash
veles export template ./my-template.tar.gz
```

동료에게 템플릿을 전달하면, 그들이 `veles import`로 가져와 대화 기록이나
원본 소스 없이 구조와 스킬을 그대로 사용할 수 있습니다.

## 어느 것을 사용할까

| 목표 | 명령어 |
|---|---|
| 프로젝트를 그대로 백업/이동 | `veles export full` |
| 데이터 없이 구조와 스킬 공유 | `veles export template` |
