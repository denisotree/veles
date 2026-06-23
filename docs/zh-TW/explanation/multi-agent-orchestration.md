# 多 agent 編排

> 🌐 **語言：** [English](../../en/explanation/multi-agent-orchestration.md) · [简体中文](../../zh-CN/explanation/multi-agent-orchestration.md) · **繁體中文** · [日本語](../../ja/explanation/multi-agent-orchestration.md) · [한국어](../../ko/explanation/multi-agent-orchestration.md) · [Español](../../es/explanation/multi-agent-orchestration.md) · [Français](../../fr/explanation/multi-agent-orchestration.md) · [Italiano](../../it/explanation/multi-agent-orchestration.md) · [Português (BR)](../../pt-BR/explanation/multi-agent-orchestration.md) · [Português (PT)](../../pt-PT/explanation/multi-agent-orchestration.md) · [Русский](../../ru/explanation/multi-agent-orchestration.md) · [العربية](../../ar/explanation/multi-agent-orchestration.md) · [हिन्दी](../../hi/explanation/multi-agent-orchestration.md) · [বাংলা](../../bn/explanation/multi-agent-orchestration.md) · [Tiếng Việt](../../vi/explanation/multi-agent-orchestration.md)

對於複雜的工作,Veles 可以把一個任務分散到一個 **manager** 與多個專門的 **worker** 子 agent 上,而不是在單一 context 中做完所有事。本頁說明這個模型;要啟用它,請參見[manager 模式](../how-to/long-running-tasks.md#manager-mode--decompose-any-prompt)。

## 結構

```
            manager  (decomposes the task, never writes the final answer)
           /    |    \
    explorer  writer  advisor   (specialised workers, run in parallel)
```

- **manager** 規劃拆解並協調——但它**不會**自己撰寫最終交付物。
- **worker** 擁有角色專屬的系統 prompt:`explorer` 蒐集、`writer` 產出答案、`advisor` 審查。這組角色是可擴展的。
- 最後,manager 會把一份簡短的報告寫入記憶。

## 沒有傳話遊戲

一條關鍵規則:中間產物**逐字**送達 synthesiser,而非經由 manager 的轉述。explorer 的發現會直接交給 writer,因此細節不會在一連串摘要中流失。這正是讓拆解能提升品質、而非稀釋品質的原因。

## 為何「manager 永不撰寫」

如果協調者也撰寫答案,它就會有抄捷徑、繞過 worker 的誘惑,失去專業分工的好處。把綜整工作保留在專責的 `writer`(餵給它逐字輸入)中,能強制執行分工。Veles 把這一點變成執行期的保證。

## 它在何時有幫助——又在何時沒有

對於範圍廣泛或多面向的任務(稽核這個程式碼庫、從多個角度研究這個問題),拆解是值得的。對於一個快速、單一 context 的請求,它只會增加額外負擔——這正是為何 manager 模式是**明確選擇加入**、預設關閉的(`veles run --manager` 或 `VELES_MANAGER_MODE=1`)。
