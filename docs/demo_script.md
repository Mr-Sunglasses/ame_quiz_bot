### Demo Script

- Start: `/start`
- Create: `/newquiz`
  - Bot: "Quiz title?"
  - You: `Cardiology Basics`
  - Bot: "Quiz description (optional)?"
  - You: `/skip`
  - Bot: "Send questions one-by-one or paste all at once. Reply `single` or `bulk`."
  - You: `bulk`
  - Bot: "Paste all questions... Then send /parse."
  - You paste bulk (Q1..Q3 as in tests) and send `/parse`
  - Bot shows preview (first 3), count, asks Proceed? (yes/no)
  - You: `yes`
  - Bot: "Set duration (minutes). Send `0` for unlimited."
  - You: `2`
  - Bot: "Public or private? Send `public` or `private`."
  - You: `public`
  - Bot: "Confirm create quiz? (yes/no)"
  - You: `yes`
  - Bot: Shows summary and shareable link: `https://t.me/<BOT_USERNAME>?start=quiz_<QUIZ_ID>`

- Taker opens the link:
  - Bot: "Start quiz" button
  - On start: shows remaining time, sends Polls (quiz type), feedback after each.
  - At end: shows score and percentage.
