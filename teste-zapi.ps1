# Teste de envio Z-API direto (skip status que pode dar 400 falso)
# Uso: .\teste-zapi.ps1 5565999998888

param(
    [Parameter(Mandatory=$true)]
    [string]$MeuNumero
)

$numLimpo = $MeuNumero -replace '[^\d]', ''
if ($numLimpo.Length -lt 12 -or $numLimpo.Length -gt 13) {
    Write-Host "Numero invalido. Use 5565999887766 (DDI+DDD+numero)" -ForegroundColor Red
    exit 1
}

$instanceId  = (Select-String -Path .env -Pattern "^ZAPI_INSTANCE_ID=(.*)$").Matches[0].Groups[1].Value
$token       = (Select-String -Path .env -Pattern "^ZAPI_TOKEN=(.*)$").Matches[0].Groups[1].Value
$clientToken = (Select-String -Path .env -Pattern "^ZAPI_CLIENT_TOKEN=(.*)$").Matches[0].Groups[1].Value
$base = "https://api.z-api.io/instances/$instanceId/token/$token"

$headers = @{ "Content-Type" = "application/json" }
if ($clientToken) { $headers["Client-Token"] = $clientToken }

Write-Host "`n=== Enviando mensagem de teste pra $numLimpo ===" -ForegroundColor Cyan
$body = @{
    phone = $numLimpo
    message = "Teste RA Motors via Z-API ($(Get-Date -Format 'HH:mm:ss')). Pipeline funcionando!"
    delayMessage = 1
} | ConvertTo-Json

try {
    $resp = Invoke-RestMethod -Uri "$base/send-text" -Method POST -Body $body -Headers $headers -TimeoutSec 20
    Write-Host "Resposta:" -ForegroundColor DarkGray
    $resp | ConvertTo-Json -Depth 4

    if ($resp.id -or $resp.zaapId -or $resp.messageId) {
        Write-Host "`nSUCESSO! Mensagem enviada (id: $($resp.id)$($resp.zaapId)$($resp.messageId))" -ForegroundColor Green
        Write-Host "Confere o WhatsApp do numero $numLimpo - deve chegar em alguns segundos." -ForegroundColor Green
    } else {
        Write-Host "`nResposta sem id de mensagem:" -ForegroundColor Yellow
    }
} catch {
    Write-Host "ERRO HTTP $($_.Exception.Response.StatusCode.value__): $($_.Exception.Message)" -ForegroundColor Red
    if ($_.Exception.Response) {
        try {
            $sr = New-Object IO.StreamReader $_.Exception.Response.GetResponseStream()
            $errBody = $sr.ReadToEnd()
            Write-Host "Body do erro: $errBody" -ForegroundColor Yellow
        } catch {}
    }
}

Write-Host "`n=== Health do webhook backend ===" -ForegroundColor Cyan
try {
    $h = Invoke-RestMethod -Uri "https://ramotors-api-cuiaba.onrender.com/webhook/zapi/health" -TimeoutSec 10
    if ($h.ok) { Write-Host "  OK: $($h.endpoint)" -ForegroundColor Green }
} catch {
    Write-Host "  Backend webhook: $($_.Exception.Message)" -ForegroundColor Yellow
}
