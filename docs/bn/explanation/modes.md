# Run modes

> 🌐 **ভাষা:** [English](../../en/explanation/modes.md) · [简体中文](../../zh-CN/explanation/modes.md) · [繁體中文](../../zh-TW/explanation/modes.md) · [日本語](../../ja/explanation/modes.md) · [한국어](../../ko/explanation/modes.md) · [Español](../../es/explanation/modes.md) · [Français](../../fr/explanation/modes.md) · [Italiano](../../it/explanation/modes.md) · [Português (BR)](../../pt-BR/explanation/modes.md) · [Português (PT)](../../pt-PT/explanation/modes.md) · [Русский](../../ru/explanation/modes.md) · [العربية](../../ar/explanation/modes.md) · [हिन्दी](../../hi/explanation/modes.md) · **বাংলা** · [Tiếng Việt](../../vi/explanation/modes.md)

TUI-তে প্রতিটি prompt একটি **run mode** দ্বারা পরিচালিত হয় — একটি স্ট্র্যাটেজি যা ঠিক করে টার্নটি
কতটা স্বায়ত্তশাসন এবং কোন tools পাবে। `Shift+Tab` দিয়ে modes ঘোরান; ক্রমটি হলো
`auto → planning → writing → goal`।

## চারটি mode

### `writing` — সরাসরি চ্যাট
সরল mode: আপনার prompt পূর্ণ toolset উপলব্ধ অবস্থায় এজেন্টের কাছে যায়, এবং সে
সাড়া দেয়। সাধারণ কাজের জন্য এটি ব্যবহার করুন যেখানে আপনি এজেন্টকে কাজ করাতে চান।

### `planning` — read-only গবেষণা + একটি plan
Mutations ব্লক করা থাকে (কোনো `write_file` নেই, কোনো `run_shell` নেই)। এজেন্ট কন্টেক্সট সংগ্রহ
করতে read/search tools ব্যবহার করে, তারপর একটি স্ট্রাকচারড plan আর্টিফ্যাক্ট তৈরি করে। কোনো কিছু
স্পর্শ করার আগে চিন্তা করার জন্য এটি ব্যবহার করুন — অথবা CLI-তে একই প্রভাবের জন্য `veles run`-এ
`--plan` পাস করুন।

### `auto` — smart routing (ডিফল্ট)
একটি দ্রুত শ্রেণীবিন্যাস ঠিক করে আপনার prompt সরাসরি অনুরোধ নাকি planning দরকার, তারপর
সেই অনুযায়ী `writing` বা `planning`-এ dispatch করে। যখন আপনি অভিপ্রায় প্রকাশ করেননি তখন এটিই
সবচেয়ে স্মার্ট fallback, যে কারণে এটিই cycle-এর ডিফল্ট প্রথম স্টপ।

### `goal` — দীর্ঘ-দিগন্তের উদ্দেশ্য
একটি বহু-ধাপের উদ্দেশ্যের জন্য একটি finite-state machine চালায়: এটি স্পষ্ট করতে আপনাকে
সাক্ষাৎকার নেয়, একটি plan নিশ্চিত করে, ধাপগুলো executes করে (advisor চেক সহ), এবং
done-condition যাচাই করে — সবই সুস্পষ্ট budgets-এর অধীনে। CLI সমতুল্য হলো
[`veles goal`](../how-to/long-running-tasks.md#goals--objectives-with-budgets-and-checkpoints)
কমান্ড পরিবার।

## modes কেন আছে

ভিন্ন অনুরোধ ভিন্ন মাত্রার সতর্কতা চায়। একটি দ্রুত প্রশ্নে আনুষ্ঠানিকতার দরকার নেই;
একটি ঝুঁকিপূর্ণ পরিবর্তন প্রথমে একটি read-only planning পাস থেকে উপকৃত হয়; একটি
বড় উদ্দেশ্যের budgets ও checkpoints দরকার। Modes এই পছন্দটিকে সুস্পষ্ট ও
প্রতি-টার্নে পরিবর্তনযোগ্য করে, পুরো সেশনে একটিমাত্র আচরণ বেক করে রাখার বদলে।

আপনি যখন সেশনের মাঝপথে পরিবর্তন করেন, এজেন্টকে নতুন নিয়মগুলো জানানো হয় তাই তার আচরণ
তৎক্ষণাৎ পরিবর্তিত হয়।
