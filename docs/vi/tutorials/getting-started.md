# Bắt đầu

> 🌐 **Languages:** **English** · [Русский](../../ru/tutorials/getting-started.md)

Trong hướng dẫn này bạn sẽ cài đặt Veles, cấp cho nó một API key, tạo dự án đầu
tiên, và chạy prompt đầu tiên. Mất khoảng 10 phút. Kết thúc bạn sẽ có một dự án
Veles hoạt động mà bạn có thể trò chuyện cùng.

## Yêu cầu trước

- **Python 3.13+** (Veles yêu cầu `>=3.13`).
- Một API key của LLM. Chúng ta sẽ dùng **OpenRouter** (nhà cung cấp mặc định);
  bất kỳ [nhà cung cấp nào khác](../reference/providers.md) cũng được, kể cả các
  nhà cung cấp hoàn toàn cục bộ không cần key.

## 1. Cài đặt

Veles được cài dưới dạng lệnh `veles` toàn cục qua [uv](https://docs.astral.sh/uv/):

```bash
# install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# install veles (published as `veles-ai`; the command is `veles`)
uv tool install veles-ai
# …or from a source checkout: uv tool install .

# verify
veles --help
```

Để cập nhật về sau: `uv tool upgrade veles-ai`.

## 2. Cấp cho Veles một API key

Lấy một key từ [openrouter.ai](https://openrouter.ai) và export nó:

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

Bạn cũng có thể lưu nó trong keychain của hệ điều hành để không phải export lại
mỗi shell:

```bash
veles secret set OPENROUTER_API_KEY
```

(Thích một thiết lập hoàn toàn cục bộ không cần key? Cài [Ollama](https://ollama.com),
`ollama pull qwen3:4b-instruct`, và dùng `--provider ollama` bên dưới.)

## 3. Tạo dự án đầu tiên

Một dự án Veles chỉ là một thư mục với một thư mục trạng thái `.veles/`. Tạo một dự án:

```bash
mkdir my-notes && cd my-notes
veles init my-notes
```

Lệnh này tạo `AGENTS.md` (ngữ cảnh dự án của bạn), `sources/` và `wiki/`
([layout LLM-Wiki](../explanation/layout-packs-and-llm-wiki.md) mặc định), và
`.veles/` (trạng thái máy). Xem [layout dự án](../reference/project-layout.md).

## 4. Chạy prompt đầu tiên

```bash
veles run "Read AGENTS.md and describe this project in three sentences."
```

Veles nạp ngữ cảnh dự án của bạn, gọi model, và in ra câu trả lời. Lượt này được
lưu vào bộ nhớ của dự án.

Thêm `--stream` để xem các token khi chúng đến, hoặc `--verbose` để xem tiến độ
từng lượt:

```bash
veles run --stream "What files exist in this project right now?"
```

## 5. Mở REPL tương tác

Để có một cuộc trò chuyện nhiều lượt, mở TUI:

```bash
veles tui
```

Gõ một tin nhắn và nhấn Enter. Các phím hữu ích: `Ctrl+D` để thoát, `Shift+Tab`
để luân chuyển [các chế độ chạy](../explanation/modes.md), `/help` để liệt kê các
slash command. Danh sách đầy đủ trong [tham khảo TUI](../reference/tui.md).

## 6. Xem những gì Veles ghi nhớ

Mỗi lần chạy đều được lưu. Liệt kê và tìm kiếm các session của bạn:

```bash
veles sessions list
veles sessions search "three sentences"
```

## Đi tiếp đâu

- **[Xây dựng cơ sở tri thức](building-a-knowledge-base.md)** — nạp các nguồn vào
  wiki và đặt câu hỏi về chúng.
- **[Cấu hình nhà cung cấp](../how-to/configure-providers.md)** — chuyển sang
  Anthropic, OpenAI, Gemini, hoặc một model hoàn toàn cục bộ.
- **[Tổng quan kiến trúc](../explanation/architecture.md)** — hiểu Veles đang làm
  gì bên trong.
