# RA Motors - Reset Evolution + recriar instance + salvar QR
# Uso: .\reset-evolution.ps1

$ErrorActionPreference = "Continue"
$compose = "docker-compose.local.yml"
$instance = "ramotors-01"

# Le EVOLUTION_KEY do .env
$envFile = ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "ERRO: arquivo .env nao encontrado em $PWD" -ForegroundColor Red
    exit 1
}
$apiKey = (Select-String -Path $envFile -Pattern "^EVOLUTION_KEY=(.*)$").Matches[0].Groups[1].Value
if (-not $apiKey) {
    Write-Host "ERRO: EVOLUTION_KEY nao encontrada no .env" -ForegroundColor Red
    exit 1
}
Write-Host "EVOLUTION_KEY carregada do .env" -ForegroundColor DarkGray

Write-Host "`n=== [1/6] Parando containers ===" -ForegroundColor Cyan
docker compose -f $compose down

Write-Host "`n=== [2/6] Apagando volumes da Evolution ===" -ForegroundColor Cyan
docker volume rm ramotors-prospect_evolution_data 2>$null
docker volume rm ramotors-prospect_evolution_pg_data 2>$null
Write-Host "  Volumes removidos (ou ja nao existiam)" -ForegroundColor Green

Write-Host "`n=== [3/6] Baixando imagem Evolution v2.1.1 ===" -ForegroundColor Cyan
docker compose -f $compose pull evolution-api

# Garante pasta qrcodes/
if (-not (Test-Path ".\qrcodes")) {
    New-Item -ItemType Directory -Path ".\qrcodes" | Out-Null
    Write-Host "  Pasta qrcodes/ criada" -ForegroundColor DarkGray
}

Write-Host "`n=== [4/6] Rebuilding webhook + subindo containers ===" -ForegroundColor Cyan
docker compose -f $compose up -d --build

Write-Host "`n=== [5/6] Aguardando Evolution bootar (35s) ===" -ForegroundColor Cyan
for ($i = 35; $i -gt 0; $i--) {
    Write-Host -NoNewline "`r  $i s..."
    Start-Sleep -Seconds 1
}
Write-Host "`r  Pronto.        " -ForegroundColor Green

# Confirma que Evolution responde
$tentativas = 0
while ($tentativas -lt 6) {
    try {
        $ping = Invoke-RestMethod -Uri "http://localhost:8080" -Method GET -TimeoutSec 5
        if ($ping.message) {
            Write-Host "  Evolution respondeu: $($ping.message)" -ForegroundColor Green
            break
        }
    } catch {
        $tentativas++
        Write-Host "  Tentativa $tentativas/6..." -ForegroundColor Yellow
        Start-Sleep -Seconds 5
    }
}
if ($tentativas -ge 6) {
    Write-Host "ERRO: Evolution nao respondeu. Cheque 'docker logs evolution-api'" -ForegroundColor Red
    exit 1
}

Write-Host "`n=== [6/6] Criando instance ===" -ForegroundColor Cyan
$headers = @{ "apikey" = $apiKey; "Content-Type" = "application/json" }

# Tenta deletar (se ja existir do volume antigo)
try {
    Invoke-RestMethod -Uri "http://localhost:8080/instance/delete/$instance" -Method DELETE -Headers $headers -TimeoutSec 5 | Out-Null
} catch {}

$body = @{
    instanceName = $instance
    qrcode = $true
    integration = "WHATSAPP-BAILEYS"
} | ConvertTo-Json

$resp = Invoke-RestMethod -Uri "http://localhost:8080/instance/create" -Method POST -Headers $headers -Body $body
Write-Host "  Instance criada (id: $($resp.instance.instanceId))" -ForegroundColor Green

# A v2.1.1 NAO retorna QR na resposta; ele vem via webhook event qrcode.updated.
# Nosso webhook_server salva em /qrcodes (mapeado para .\qrcodes do host).
$qrPath = ".\qrcodes\$instance.png"
$qrFull = (Resolve-Path ".\qrcodes" -ErrorAction SilentlyContinue).Path
Write-Host "`nAguardando webhook entregar o QR Code..." -ForegroundColor Cyan
Write-Host "  Pasta monitorada: $qrFull" -ForegroundColor DarkGray

$timeout = 60
$elapsed = 0
$achou = $false
while ($elapsed -lt $timeout) {
    if (Test-Path $qrPath) {
        $achou = $true
        break
    }
    Start-Sleep -Seconds 2
    $elapsed += 2
    Write-Host -NoNewline "`r  $elapsed s..."
}
Write-Host ""

if ($achou) {
    $qrAbs = (Resolve-Path $qrPath).Path
    Write-Host "`n  QR Code recebido: $qrAbs" -ForegroundColor Green
    Write-Host "  Abrindo automaticamente..." -ForegroundColor Green
    Start-Process $qrAbs
    Write-Host "`n=== TUDO PRONTO ===" -ForegroundColor Magenta
    Write-Host "Escaneia o QR com o WhatsApp do CHIP DA EMPRESA." -ForegroundColor White
    Write-Host "WhatsApp -> Aparelhos conectados -> Conectar um aparelho" -ForegroundColor White
    Write-Host "`nApos conectar, me avisa para reativar beat/loop-envios." -ForegroundColor White
} else {
    Write-Host "`n  QR nao chegou em ${timeout}s." -ForegroundColor Yellow
    Write-Host "  Veja os logs do webhook:" -ForegroundColor Yellow
    Write-Host "    docker logs ramotors-webhook --tail 30" -ForegroundColor White
    Write-Host "  E os da Evolution:" -ForegroundColor Yellow
    Write-Host "    docker logs evolution-api --tail 30" -ForegroundColor White
}
