# Bố cục dự án & trạng thái

> 🌐 **Ngôn ngữ:** [English](../../en/reference/project-layout.md) · [简体中文](../../zh-CN/reference/project-layout.md) · [繁體中文](../../zh-TW/reference/project-layout.md) · [日本語](../../ja/reference/project-layout.md) · [한국어](../../ko/reference/project-layout.md) · [Español](../../es/reference/project-layout.md) · [Français](../../fr/reference/project-layout.md) · [Italiano](../../it/reference/project-layout.md) · [Português (BR)](../../pt-BR/reference/project-layout.md) · [Português (PT)](../../pt-PT/reference/project-layout.md) · [Русский](../../ru/reference/project-layout.md) · [العربية](../../ar/reference/project-layout.md) · [हिन्दी](../../hi/reference/project-layout.md) · [বাংলা](../../bn/reference/project-layout.md) · **Tiếng Việt**

`veles init` tạo ra những gì, Veles lưu trạng thái ở đâu, và schema bộ nhớ dự án.

## `veles init` tạo ra những gì

Nửa nội dung-người-dùng phụ thuộc vào layout pack được chọn (`--layout`,
mặc định `llm-wiki`); nửa trạng thái `.veles/` thì giống nhau ở mọi nơi.

```
my-project/                  # veles init  (default llm-wiki layout)
├── AGENTS.md                # project context (injected into the agent)
├── CLAUDE.md → AGENTS.md    # symlink, so a `claude` CLI picks up the same context
├── GEMINI.md → AGENTS.md    # symlink, for a `gemini` CLI
├── sources/                 # raw, immutable source material (agent-readonly)
├── wiki/                    # the LLM-writable knowledge zone
│   ├── concepts/ entities/ queries/ self-doc/ sessions/
└── .veles/                  # project state (do not commit; machine-managed)
    ├── project.toml         # name, created_at, schema_version, layout
    ├── memory.db            # SQLite: sessions, turns, insights, rules, telemetry
    ├── memory/              # the agent's own memory artefacts:
    │   ├── LOG.md           #   append-only system-ops journal
    │   ├── insights/        #   rendered views of `insights` rows
    │   ├── sessions/        #   compaction summaries
    │   └── proposals/       #   subproject / skill-promotion proposals
    ├── jobs/                # scheduled-job outputs
    └── skills/              # project-local skills
```

Với `--layout notes`, nửa nội dung chỉ là một thư mục `notes/` duy nhất; với
`--layout bare` thì hoàn toàn không có scaffold nội dung nào. `wiki/INDEX.md` (catalog
theo nhu cầu) được tạo khi wiki lớn dần; `config.toml`, `tools/`, và `plans/` xuất
hiện dưới `.veles/` khi bạn cấu hình một thứ gì đó, khi agent viết ra một công cụ,
hoặc khi bạn chạy một goal.

## Các thư mục trạng thái

| Đường dẫn | Phạm vi | Có commit không? |
|---|---|---|
| `<project>/AGENTS.md` + nội dung layout (`wiki/`, `sources/`, `notes/`, …) | Nội dung dự án | **Có** — đây là cơ sở tri thức của bạn |
| `<project>/.veles/` | Trạng thái máy của dự án (bộ nhớ, cấu hình, skill/tool cục bộ) | Không |
| `~/.veles/` | Toàn cục cấp người dùng: `config.toml`, các quyền trust, skill/tool dùng chung giữa các dự án, layout pack, model cache, locale | Không |

`VELES_USER_HOME` chuyển hướng `~` cho cây thư mục toàn cục cấp người dùng (kiểm thử, sandbox).

## Bộ nhớ dự án (`.veles/memory.db` + `.veles/memory/`)

Bộ nhớ dự án của Veles là một **artefact có cấu trúc**, tách biệt khỏi nội dung của
bạn và độc lập với layout. Cơ sở dữ liệu SQLite (chế độ WAL) là nguồn sự thật;
`.veles/memory/` giữ phần con-người-đọc-được (các view insight đã render, các bản
tóm tắt session, các đề xuất, nhật ký system-ops). Các bảng chính:

| Bảng | Lưu giữ |
|---|---|
| `sessions`, `turns` | Lịch sử hội thoại (mỗi turn một hàng) |
| `turns_fts` | Chỉ mục toàn văn trên các turn (hỗ trợ `veles sessions search`) |
| `insights`, `insights_fts`, `insight_refs` | Insight đã học (các hàng chuẩn; các view markdown có thể tái tạo) + liên kết dedup |
| `rules`, `rules_fts` | Các quy tắc format/do/don't/preference được tiêm vào stable prompt |
| `skills`, `skill_uses`, `skill_tool_refs` | Registry skill + telemetry + liên kết tool |
| `tools`, `tool_uses` | Registry tool + telemetry (số lần dùng/thành công/lỗi) |
| `project_tree` | Bản đồ tệp dự án được cache + tag ngữ nghĩa để xếp hạng độ liên quan |

Xem [Bộ nhớ dự án & vòng lặp học hỏi](../explanation/project-memory-and-learning-loop.md)
để biết cách chúng được ghi và recall.

## Layout pack

`veles init --layout {llm-wiki|notes|bare|<custom>}` chọn layout nội dung; pack sở
hữu scaffold, template AGENTS.md, các vùng cho phép ghi, và việc engine wiki (các
công cụ wiki, tiêm prompt INDEX, recall wiki) có hoạt động hay không. Xem
[layout pack & LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md).
