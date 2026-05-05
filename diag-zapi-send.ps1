# Diagnostico detalhado de envio Z-API
# Uso: .\diag-zapi-send.ps1 5565999998888

param(
    [Parameter(Mandatory=$true)]
    [string]$Numero
)

$numLimpo = $Numero -replace '[^\d]', ''

$instanceId = (Select-String -Path .env -Pattern "^ZAPI_INSTANCE_ID=(.*)$").Matches[0].Groups[1].Value
$token      = (Select-String -Path .env -Pattern "^ZAPI_TOKEN=(.*)$").Matches[0].Groups[1].Value
$base = "https://api.z-api.io/instances/$instanceId/token/$token"

function FullDebug {
    param($url, $body, $label)
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "TESTE: $label" -ForegroundColor Cyan
    Write-Host "URL: $url" -ForegroundColor DarkGray
    Write-Host "BODY: $body" -ForegroundColor DarkGray
    Write-Host "----------------------------------------" -ForegroundColor DarkGray
    try {
        $req = [System.Net.HttpWebRequest]::Create($url)
        $req.Method = "POST"
        $req.ContentType = "application/json"
        $req.Timeout = 20000
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
        $req.ContentLength = $bytes.Length
        $stream = $req.GetRequestStream()
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Close()

        $resp = $req.GetResponse()
        $rsr = New-Object IO.StreamReader $resp.GetResponseStream()
        $respBody = $rsr.ReadToEnd()
        Write-Host "STATUS: $([int]$resp.StatusCode) $($resp.StatusCode)" -ForegroundColor Green
        Write-Host "RESPONSE: $respBody" -ForegroundColor Green
        $resp.Close()
    } catch [System.Net.WebException] {
        $errResp = $_.Exception.Response
        if ($errResp) {
            $code = [int]$errResp.StatusCode
            Write-Host "STATUS: $code $($errResp.StatusCode)" -ForegroundColor Red
            try {
                $rsr = New-Object IO.StreamReader $errResp.GetResponseStream()
                $errBody = $rsr.ReadToEnd()
                if ($errBody) {
                    Write-Host "ERROR BODY: $errBody" -ForegroundColor Yellow
                } else {
                    Write-Host "ERROR BODY: (vazio)" -ForegroundColor Yellow
                }
                # Headers de resposta
                Write-Host "HEADERS:" -ForegroundColor DarkGray
                $errResp.Headers.AllKeys | ForEach-Object {
                    Write-Host "  $_ : $($errResp.Headers[$_])" -ForegroundColor DarkGray
                }
            } catch {
                Write-Host "Falha ao ler corpo do erro" -ForegroundColor Yellow
            }
        } else {
            Write-Host "Sem resposta HTTP: $($_.Exception.Message)" -ForegroundColor Red
        }
    }
}

# 1. Payload basico
$b1 = '{"phone":"' + $numLimpo + '","message":"Teste 1 simples"}'
FullDebug -url "$base/send-text" -body $b1 -label "send-text payload basico"

# 2. Com delayMessage
$b2 = '{"phone":"' + $numLimpo + '","message":"Teste 2 com delay","delayMessage":1}'
FullDebug -url "$base/send-text" -body $b2 -label "send-text com delayMessage"

# 3. Endpoint alternativo /send-message
FullDebug -url "$base/send-message" -body $b1 -label "send-message (endpoint alternativo)"

# 4. Endpoint /send-messages
FullDebug -url "$base/send-messages" -body $b1 -label "send-messages (plural)"

# 5. Status alternativo
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "TESTE: GET /device" -ForegroundColor Cyan
try {
    $r = Invoke-RestMethod -Uri "$base/device" -Method GET -TimeoutSec 10
    Write-Host "RESPONSE:" -ForegroundColor Green
    $r | ConvertTo-Json -Depth 4
} catch {
    Write-Host "ERRO: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n========================================" -ForegroundColor Magenta
Write-Host "Manda este output completo pro Claude" -ForegroundColor Magenta
