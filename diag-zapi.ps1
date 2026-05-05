# Diagnostico Z-API - tenta varios endpoints e mostra body do erro
# Uso: .\diag-zapi.ps1

$instanceId = (Select-String -Path .env -Pattern "^ZAPI_INSTANCE_ID=(.*)$").Matches[0].Groups[1].Value
$token      = (Select-String -Path .env -Pattern "^ZAPI_TOKEN=(.*)$").Matches[0].Groups[1].Value
$clientToken = (Select-String -Path .env -Pattern "^ZAPI_CLIENT_TOKEN=(.*)$").Matches[0].Groups[1].Value

Write-Host "Instance ID: $instanceId" -ForegroundColor DarkGray
Write-Host "Token: $($token.Substring(0,8))..." -ForegroundColor DarkGray
Write-Host "Client-Token configurado: $([bool]$clientToken)" -ForegroundColor DarkGray

$base = "https://api.z-api.io/instances/$instanceId/token/$token"

function TestarEndpoint {
    param($url, $method, $body, $headers, $label)
    Write-Host "`n--- $label ---" -ForegroundColor Cyan
    Write-Host "  $method $url" -ForegroundColor DarkGray
    if ($headers.Count -gt 0) {
        Write-Host "  Headers: $($headers | ConvertTo-Json -Compress)" -ForegroundColor DarkGray
    }
    try {
        $params = @{ Uri = $url; Method = $method; TimeoutSec = 10; Headers = $headers }
        if ($body) {
            $params.Body = $body
            $params.ContentType = "application/json"
        }
        $resp = Invoke-RestMethod @params
        Write-Host "  OK:" -ForegroundColor Green
        $resp | ConvertTo-Json -Depth 4
    } catch {
        Write-Host "  HTTP $($_.Exception.Response.StatusCode.value__): $($_.Exception.Message)" -ForegroundColor Red
        if ($_.Exception.Response) {
            try {
                $sr = New-Object IO.StreamReader $_.Exception.Response.GetResponseStream()
                $errBody = $sr.ReadToEnd()
                Write-Host "  Body: $errBody" -ForegroundColor Yellow
            } catch {}
        }
    }
}

$h1 = @{}
$h2 = @{ "Client-Token" = $clientToken }

TestarEndpoint -url "$base/status" -method "GET" -headers $h1 -label "Status SEM Client-Token"

if ($clientToken) {
    TestarEndpoint -url "$base/status" -method "GET" -headers $h2 -label "Status COM Client-Token"
} else {
    Write-Host "`n--- Status COM Client-Token: PULADO (vazio no .env) ---" -ForegroundColor DarkYellow
}

TestarEndpoint -url "$base/qr-code" -method "GET" -headers $h1 -label "QR Code (deve dar 'instancia ja conectada' ou retornar QR)"

TestarEndpoint -url "$base/instance-info" -method "GET" -headers $h1 -label "Info da instancia (alternativa)"

TestarEndpoint -url "$base/me" -method "GET" -headers $h1 -label "Endpoint /me"

Write-Host "`n=== Diagnostico ===" -ForegroundColor Magenta
Write-Host "Veja qual endpoint retornou OK." -ForegroundColor White
Write-Host "Se TODOS deram 4xx -> precisa do Client-Token. Pega no painel Z-API." -ForegroundColor White
Write-Host "Se 'qr-code' retornou QR -> WhatsApp NAO foi escaneado ainda no painel." -ForegroundColor White
Write-Host "Se 'instance-info' funcionou mas /status nao -> e mudanca de API; ajustamos cliente." -ForegroundColor White
