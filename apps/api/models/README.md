# apps/api/models — tempat bobot lokal (tidak masuk Git)

Letakkan bobot model tanaman di sini, mis. `apps\api\models\best.pt`. Folder ini di-ignore Git kecuali README ini.

`models\best.pt` adalah **path berkas**, bukan perintah. Mengetiknya sendirian di PowerShell menghasilkan error
`The term 'models\best.pt' is not recognized ...`. Berikan path itu sebagai nilai parameter:

```powershell
cd apps\api
powershell -ExecutionPolicy Bypass -File .\scripts\check-model.ps1 -ModelPath .\models\best.pt -LabelMap 'jagung=plant'
powershell -ExecutionPolicy Bypass -File .\scripts\run-with-model.ps1 -ModelPath .\models\best.pt -LabelMap 'jagung=plant'
```

Dari mana `best.pt`? Hasil training dataset Anda sendiri (`ml\train.py`, lihat `ml\README.md`), atau diberikan
tim ML. Aplikasi dan skrip tidak pernah mengunduh bobot.
