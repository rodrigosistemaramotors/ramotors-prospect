# RA Motors - Diagnostico de rede da Evolution
# Uso: .\diag-evolution.ps1

Write-Host "`n=== [1] DNS dentro do container Evolution ===" -ForegroundColor Cyan
docker exec evolution-api sh -c "getent hosts web.whatsapp.com 2>&1; getent hosts mmg.whatsapp.net 2>&1; getent hosts webhook 2>&1"

Write-Host "`n=== [2] HTTP/HTTPS para WhatsApp servers ===" -ForegroundColor Cyan
docker exec evolution-api sh -c "wget -q -T 8 -O - https://web.whatsapp.com/ 2>&1 | head -3; echo '---'; wget -q -T 8 -O - https://w.whatsapp.net/ 2>&1 | head -3"

Write-Host "`n=== [3] Conectividade webhook -> webhook container ===" -ForegroundColor Cyan
docker exec evolution-api sh -c "wget -q -T 5 -O - http://webhook:9000/health 2>&1 | head -3"

Write-Host "`n=== [4] Versao Node + variaveis Evolution ===" -ForegroundColor Cyan
docker exec evolution-api sh -c "node --version 2>&1; echo '---'; env | grep -E '^(SERVER_|DATABASE_|WEBHOOK_|CONFIG_|QRCODE_|CACHE_)' | sort"

Write-Host "`n=== [5] Logs Evolution - linhas com 'error' ou 'fail' ===" -ForegroundColor Cyan
docker logs evolution-api 2>&1 | Select-String -Pattern "error|fail|reject|denied|refused|timeout|disconnect|qrcode" -CaseSensitive:$false | Select-Object -Last 30

Write-Host "`n=== [6] Status containers ===" -ForegroundColor Cyan
docker compose -f docker-compose.local.yml ps

Write-Host "`nCopia tudo isso e manda pro Claude" -ForegroundColor Yellow
