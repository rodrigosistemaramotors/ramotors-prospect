# Deploy migracao Z-API: commit + push + rebuild local
# Uso: .\deploy-zapi.ps1

Write-Host "`n=== [1/5] Commit + push para Render redeployar backend ===" -ForegroundColor Cyan
git add backend/app/routers/webhook_zapi.py backend/app/main.py backend/app/config.py worker/app/whatsapp/zapi_client.py worker/app/whatsapp/evolution_client.py worker/app/whatsapp/__init__.py worker/app/config.py docker-compose.local.yml deploy-zapi.ps1 .env.example 2>$null
git status --short
git commit -m "Migra Evolution API para Z-API + webhook publico no backend"
git push origin main
Write-Host "  Push enviado. Render vai detectar e redeployar (~2-3 min)." -ForegroundColor Green

Write-Host "`n=== [2/5] Parando containers locais antigos ===" -ForegroundColor Cyan
docker compose -f docker-compose.local.yml down

# Tambem para containers Evolution antigos se ainda estiverem rodando
docker stop evolution-api evolution-postgres ramotors-webhook 2>$null
docker rm evolution-api evolution-postgres ramotors-webhook 2>$null

Write-Host "`n=== [3/5] Removendo volumes Evolution antigos ===" -ForegroundColor Cyan
docker volume rm ramotors-prospect_evolution_data 2>$null
docker volume rm ramotors-prospect_evolution_pg_data 2>$null
Write-Host "  Volumes Evolution limpos" -ForegroundColor Green

Write-Host "`n=== [4/5] Rebuilding worker + subindo (3 containers agora) ===" -ForegroundColor Cyan
docker compose -f docker-compose.local.yml up -d --build

Start-Sleep -Seconds 5
docker compose -f docker-compose.local.yml ps

Write-Host "`n=== [5/5] Aguardando Render redeployar ===" -ForegroundColor Cyan
Write-Host "Pode levar 2-3 min. Vou checar quando o backend voltar..." -ForegroundColor DarkGray

$tentativas = 0
$maxTentativas = 30  # 5 min total
while ($tentativas -lt $maxTentativas) {
    try {
        $resp = Invoke-RestMethod -Uri "https://ramotors-api-cuiaba.onrender.com/webhook/zapi/health" -TimeoutSec 8
        if ($resp.ok) {
            Write-Host "`n  Backend redeployado e endpoint /webhook/zapi/health esta vivo!" -ForegroundColor Green
            break
        }
    } catch {
        $tentativas++
        Write-Host -NoNewline "`r  Tentativa $tentativas/$maxTentativas (Render ainda fazendo deploy)..."
        Start-Sleep -Seconds 10
    }
}

if ($tentativas -ge $maxTentativas) {
    Write-Host "`n  Render demorou demais. Cheque o deploy manual em https://dashboard.render.com" -ForegroundColor Yellow
} else {
    Write-Host "`n=== TUDO PRONTO ===" -ForegroundColor Magenta
    Write-Host "`nProximo passo: configurar webhook URL na Z-API." -ForegroundColor White
    $secret = (Select-String -Path .env -Pattern "^ZAPI_WEBHOOK_SECRET=(.*)$").Matches[0].Groups[1].Value
    Write-Host "`nURL para colar no painel Z-API (Configuracoes da instancia -> Webhooks):" -ForegroundColor Yellow
    Write-Host "  https://ramotors-api-cuiaba.onrender.com/webhook/zapi?secret=$secret" -ForegroundColor Cyan
    Write-Host "`nEvento a marcar: 'Mensagem Recebida' (ReceivedCallback)" -ForegroundColor Yellow
}
