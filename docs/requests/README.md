# Change request antar agen

Frontend (Codex) menulis `codex-<topik>.md` di sini pada branch-nya. Backend (Claude) membacanya lewat
`git show agent/codex-frontend:docs/requests/codex-<topik>.md` dan menjawab dengan commit kontrak baru.

Template:

```markdown
# CR: <judul singkat>
- Diajukan oleh / tanggal / branch+SHA:
- Alasan (kebutuhan UI konkret):
- Usulan request/response (JSON):
- Kompatibilitas (breaking? field opsional?):
- Acceptance (bagaimana tahu sudah benar):
```
