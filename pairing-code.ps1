# Tenta conectar via Pairing Code (alternativa ao QR)
# Uso: .\pairing-code.ps1 +5565999998888

param(
    [Parameter(Mandatory=$true)]
    [string]$Numero
)

# Sanitiza numero (so digitos)
$numLimpo = $Numero -replace '[^\d]', ''
if ($numLimpo.Length -lt 12 -or $numLimpo.Length -gt 13) {
    Write-Host "Numero invalido. Use formato 5565999998888 (DDI+DDD+numero, 12 ou 13 digitos)" -ForegroundColor Red
    exit 1
}
Write-Host "Numero do chip da empresa: $numLimpo" -ForegroundColor Cyan

$apiKey = (Select-String -Path .env -Pattern "^EVOLUTION_KEY=(.*)$").Matches[0].Groups[1].Value
$headers = @{ "apikey" = $apiKey; "Content-Type" = "application/json" }
$instance = "ramotors-01"

Write-Host "`nDeletando instance antiga..." -ForegroundColor DarkGray
try { Invoke-RestMethod -Uri "http://localhost:8080/instance/delete/$instance" -Method DELETE -Headers $headers -TimeoutSec 5 | Out-Null } catch {}
Start-Sleep -Seconds 2

Write-Host "Criando instance com pairing code..." -ForegroundColor Cyan
$body = @{
    instanceName = $instance
    qrcode = $true
    number = $numLimpo
    integration = "WHATSAPP-BAILEYS"
} | ConvertTo-Json

$resp = Invoke-RestMethod -Uri "http://localhost:8080/instance/create" -Method POST -Headers $headers -Body $body

Write-Host "`n=== RESPOSTA ===" -ForegroundColor Magenta
$resp | ConvertTo-Json -Depth 6

# Pairing code pode vir em varios lugares
$code = $null
if ($resp.pairingCode) { $code = $resp.pairingCode }
elseif ($resp.qrcode -and $resp.qrcode.pairingCode) { $code = $resp.qrcode.pairingCode }
elseif ($resp.code) { $code = $resp.code }

if (-not $code) {
    # Espera 5s e pega via /connect endpoint
    Start-Sleep -Seconds 5
    Write-Host "`nPedindo codigo via /connect..." -ForegroundColor Cyan
    try {
        $connectResp = Invoke-RestMethod -Uri "http://localhost:8080/instance/connect/$instance" -Method GET -Headers $headers
        $connectResp | ConvertTo-Json -Depth 6
        if ($connectResp.pairingCode) { $code = $connectResp.pairingCode }
        elseif ($connectResp.code) { $code = $connectResp.code }
    } catch {
        Write-Host "Erro: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

if ($code) {
    Write-Host "`n========================================" -ForegroundColor Green
    Write-Host "  CODIGO DE PAREAMENTO: $code" -ForegroundColor Green -BackgroundColor Black
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Como usar no celular do CHIP DA EMPRESA:" -ForegroundColor Yellow
    Write-Host "  1. Abre WhatsApp" -ForegroundColor White
    Write-Host "  2. 3 pontinhos (Android) ou Configuracoes (iPhone)" -ForegroundColor White
    Write-Host "  3. Aparelhos conectados" -ForegroundColor White
    Write-Host "  4. Conectar um aparelho" -ForegroundColor White
    Write-Host "  5. Tocar em 'Conectar com numero de telefone'" -ForegroundColor White
    Write-Host "  6. Digita: $code" -ForegroundColor White
    Write-Host ""
    Write-Host "Codigo expira em ~3 minutos." -ForegroundColor Yellow
    Write-Host "`nMonitorando conexao..." -ForegroundColor Cyan

    # Loop esperando conexao
    for ($i = 1; $i -le 60; $i++) {
        Start-Sleep -Seconds 3
        try {
            $st = Invoke-RestMethod -Uri "http://localhost:8080/instance/fetchInstances?instanceName=$instance" -Method GET -Headers $headers
            $estado = $null
            if ($st.value -and $st.value.Count -gt 0) {
                $estado = $st.value[0].connectionStatus
            } elseif ($st.Count -gt 0) {
                $estado = $st[0].connectionStatus
            }
            if ($estado -eq "open" -or $estado -eq "connected") {
                Write-Host "`nCONECTADO! Status: $estado" -ForegroundColor Green
                exit 0
            }
            Write-Host -NoNewline "`r  Status: $estado ($($i*3)s)..."
        } catch {
            Write-Host -NoNewline "`r  ($($i*3)s)..."
        }
    }
    Write-Host "`nTimeout. Codigo expirou ou nao foi digitado." -ForegroundColor Yellow
} else {
    Write-Host "`nNao consegui obter codigo de pareamento." -ForegroundColor Red
    Write-Host "Logs:" -ForegroundColor DarkGray
    docker logs evolution-api --tail 30
}
