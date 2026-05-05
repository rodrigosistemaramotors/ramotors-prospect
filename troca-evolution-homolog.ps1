# Troca para Evolution :homolog (Baileys mais novo)
# Uso: .\troca-evolution-homolog.ps1

$compose = "docker-compose.local.yml"
$instance = "ramotors-01"

# Carrega EVOLUTION_KEY
$apiKey = (Select-String -Path .env -Pattern "^EVOLUTION_KEY=(.*)$").Matches[0].Groups[1].Value

Write-Host "`n=== [1/5] Parando containers ===" -ForegroundColor Cyan
docker compose -f $compose down

Write-Host "`n=== [2/5] Apagando volumes Evolution (forca DB schema novo) ===" -ForegroundColor Cyan
docker volume rm ramotors-prospect_evolution_data 2>$null
docker volume rm ramotors-prospect_evolution_pg_data 2>$null
Write-Host "  Volumes removidos" -ForegroundColor Green

Write-Host "`n=== [3/5] Baixando imagem :homolog (~1-2 min) ===" -ForegroundColor Cyan
docker compose -f $compose pull evolution-api

Write-Host "`n=== [4/5] Subindo containers ===" -ForegroundColor Cyan
Remove-Item .\qrcodes\*.png -ErrorAction SilentlyContinue
docker compose -f $compose up -d --build

Write-Host "`n=== [5/5] Aguardando bootar (40s) ===" -ForegroundColor Cyan
Start-Sleep -Seconds 40

# Verifica Evolution
$tentativas = 0
while ($tentativas -lt 6) {
    try {
        $ping = Invoke-RestMethod -Uri "http://localhost:8080" -Method GET -TimeoutSec 5
        if ($ping.message) {
            Write-Host "  Evolution :homolog respondeu: $($ping.message)" -ForegroundColor Green
            if ($ping.version) { Write-Host "  Versao: $($ping.version)" -ForegroundColor Green }
            break
        }
    } catch {
        $tentativas++
        Start-Sleep -Seconds 5
    }
}

Write-Host "`n=== Criando instance ===" -ForegroundColor Cyan
$headers = @{ "apikey" = $apiKey; "Content-Type" = "application/json" }
try { Invoke-RestMethod -Uri "http://localhost:8080/instance/delete/$instance" -Method DELETE -Headers $headers -TimeoutSec 5 | Out-Null } catch {}
Start-Sleep -Seconds 2
$body = @{ instanceName = $instance; qrcode = $true; integration = "WHATSAPP-BAILEYS" } | ConvertTo-Json
$resp = Invoke-RestMethod -Uri "http://localhost:8080/instance/create" -Method POST -Headers $headers -Body $body
Write-Host "  Instance criada (id: $($resp.instance.instanceId))" -ForegroundColor Green

Write-Host "`n=== Aguardando QR (60s) ===" -ForegroundColor Cyan
$qrPath = ".\qrcodes\$instance.png"
$achou = $false
for ($i = 1; $i -le 30; $i++) {
    if (Test-Path $qrPath) {
        $achou = $true
        break
    }
    Start-Sleep -Seconds 2
    Write-Host -NoNewline "`r  $($i*2) s..."
}
Write-Host ""

if ($achou) {
    $qrAbs = (Resolve-Path $qrPath).Path
    Write-Host "`nSUCESSO! QR salvo: $qrAbs" -ForegroundColor Green
    Start-Process $qrAbs
    Write-Host "Escaneia com o WhatsApp do CHIP DA EMPRESA" -ForegroundColor Magenta
} else {
    Write-Host "`nQR ainda nao chegou. Salvando logs detalhados..." -ForegroundColor Yellow
    docker logs evolution-api --tail 100 > evolution-debug.log 2>&1
    Write-Host "Logs salvos em: $(Resolve-Path .\evolution-debug.log)" -ForegroundColor Yellow
    Write-Host "Manda esse arquivo pro Claude" -ForegroundColor Yellow
    Write-Host "`nUltimas 30 linhas:" -ForegroundColor DarkGray
    Get-Content .\evolution-debug.log -Tail 30
}
