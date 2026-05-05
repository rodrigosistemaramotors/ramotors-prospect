# Teste end-to-end: cria anuncio + conversa fake, deixa loop-envios mandar,
# e voce responde no WhatsApp pra ver a IA classificando e respondendo.
# Uso: .\teste-end-to-end.ps1 5565996236037

param(
    [Parameter(Mandatory=$true)]
    [string]$MeuNumero
)

$ErrorActionPreference = "Stop"

$numLimpo = $MeuNumero -replace '[^\d]', ''
if ($numLimpo.Length -lt 12 -or $numLimpo.Length -gt 13) {
    Write-Host "Numero invalido. Use 5565999887766" -ForegroundColor Red
    exit 1
}
$telefoneCom = "+$numLimpo"

$backend = "https://ramotors-api-cuiaba.onrender.com"
$workerKey = (Select-String -Path .env -Pattern "^WORKER_API_KEY=(.*)$").Matches[0].Groups[1].Value

# 1. Login como admin
Write-Host "`n=== [1/6] Login admin ===" -ForegroundColor Cyan
$loginBody = @{ email = "admin@ramotors.com"; senha = "RAMotors2026!" } | ConvertTo-Json
$loginResp = Invoke-RestMethod -Uri "$backend/auth/login" -Method POST -Body $loginBody -ContentType "application/json"
$jwt = $loginResp.access_token
$authHeader = @{ "Authorization" = "Bearer $jwt" }
Write-Host "  JWT obtido" -ForegroundColor Green

# 2. Listar e ativar instancia
Write-Host "`n=== [2/6] Ativando instancia WhatsApp ===" -ForegroundColor Cyan
$insts = Invoke-RestMethod -Uri "$backend/instancias-whatsapp" -Method GET -Headers $authHeader
if (-not $insts -or $insts.Count -eq 0) {
    Write-Host "ERRO: nenhuma instancia cadastrada no banco. Cadastra uma primeiro." -ForegroundColor Red
    exit 1
}
$inst = $insts[0]
Write-Host "  Instancia $($inst.id) - status $($inst.status) - $($inst.evolution_instance_id)" -ForegroundColor DarkGray

if ($inst.status -ne "ATIVA") {
    Invoke-RestMethod -Uri "$backend/instancias-whatsapp/$($inst.id)/ativar" -Method POST -Headers $authHeader | Out-Null
    Write-Host "  Instancia ativada" -ForegroundColor Green
} else {
    Write-Host "  Ja estava ATIVA" -ForegroundColor Green
}

# 3. Criar anuncio fake apontando pro telefone do usuario
Write-Host "`n=== [3/6] Criando anuncio fake ===" -ForegroundColor Cyan
$hash = "teste-" + [Guid]::NewGuid().ToString("N").Substring(0, 16)
$anuncioBody = @{
    anuncios = @(
        @{
            fonte = "OLX"
            url = "https://olx.com.br/teste-$hash"
            url_canonica = "olx.com.br/teste-$hash"
            titulo = "Teste - Honda Civic 2020 EXL CVT"
            modelo = "Civic"
            marca = "Honda"
            ano = 2020
            km = 45000
            preco = 95000
            cidade = "Cuiaba-MT"
            bairro = "Centro"
            nome_vendedor = "Rodrigo Teste"
            telefone = $telefoneCom
            descricao = "Teste end-to-end RA Motors"
            vendedor_tipo = "PARTICULAR"
            hash_unico = $hash
            fotos_urls = @()
            dados_extras = @{ teste = $true }
        }
    )
} | ConvertTo-Json -Depth 6

$workerHeader = @{ "X-Worker-Key" = $workerKey; "Content-Type" = "application/json" }
$anuncioResp = Invoke-RestMethod -Uri "$backend/anuncios/lote" -Method POST -Body $anuncioBody -Headers $workerHeader
Write-Host "  Anuncio criado:" -ForegroundColor Green
$anuncioResp | ConvertTo-Json -Depth 4

if ($anuncioResp.novos -eq 0) {
    Write-Host "  Anuncio descartado (talvez telefone ja em uso). Motivos: $($anuncioResp.motivos_descarte | ConvertTo-Json)" -ForegroundColor Yellow
    Write-Host "  Tentando mesmo assim - pode ja existir conversa anterior." -ForegroundColor Yellow
}

# 4. Disparar geracao de mensagem (a IA vai escrever a abordagem inicial)
Write-Host "`n=== [4/6] Gerando mensagem inicial via IA ===" -ForegroundColor Cyan
$gen = Invoke-RestMethod -Uri "$backend/conversas/gerar-mensagens-pendentes?limite=5" -Method POST -Headers $workerHeader
Write-Host "  Resultado: $($gen | ConvertTo-Json)" -ForegroundColor Green

if ($gen.geradas -eq 0) {
    Write-Host "  Nenhuma mensagem gerada. Pode ser que ja exista conversa pra esse telefone." -ForegroundColor Yellow
    Write-Host "  Continuando assim mesmo - loop-envios talvez ja tenha pendente da rodada anterior." -ForegroundColor Yellow
}

# 5. Aguardar loop-envios pegar e enviar
Write-Host "`n=== [5/6] Aguardando loop-envios mandar (ate 4 min, com delay aleatorio 60-180s) ===" -ForegroundColor Cyan
Write-Host "  O sistema espera 60-180s antes de enviar pra parecer humano." -ForegroundColor DarkGray
Write-Host "  Confere o WhatsApp do numero $numLimpo durante este tempo..." -ForegroundColor White

# Polling no log do loop-envios
$inicio = Get-Date
$enviada = $false
while (((Get-Date) - $inicio).TotalSeconds -lt 240) {
    $log = docker logs ramotors-loop-envios --tail 5 2>&1 | Out-String
    if ($log -match "enviada") {
        Write-Host "`n  Logs do loop-envios mostram envio:" -ForegroundColor Green
        docker logs ramotors-loop-envios --tail 10 2>&1
        $enviada = $true
        break
    }
    Start-Sleep -Seconds 5
    $secs = [int]((Get-Date) - $inicio).TotalSeconds
    Write-Host -NoNewline "`r  ${secs}s aguardando envio..."
}
Write-Host ""

if (-not $enviada) {
    Write-Host "`n  Nao detectei envio em 4 min. Logs do loop-envios:" -ForegroundColor Yellow
    docker logs ramotors-loop-envios --tail 30
    Write-Host "`n  Logs do worker:" -ForegroundColor Yellow
    docker logs ramotors-worker --tail 20
}

# 6. Aguardar usuario responder
Write-Host "`n=== [6/6] AGORA E SUA VEZ ===" -ForegroundColor Magenta
Write-Host "1. Confere se a mensagem chegou no WhatsApp de $numLimpo" -ForegroundColor White
Write-Host "2. Responde com algo tipo 'oi, tenho interesse' ou 'qual a proposta?'" -ForegroundColor White
Write-Host "3. A Z-API vai disparar webhook -> backend -> IA classifica -> resposta automatica" -ForegroundColor White
Write-Host ""
Write-Host "Vou monitorar logs por 5 minutos. Mande sua resposta agora..." -ForegroundColor Cyan
Write-Host ""

$inicio2 = Get-Date
$ultimaLinha = ""
while (((Get-Date) - $inicio2).TotalSeconds -lt 300) {
    Start-Sleep -Seconds 4
    $logsLoopEnvios = docker logs ramotors-loop-envios --tail 5 2>&1 | Out-String
    if ($logsLoopEnvios -ne $ultimaLinha -and $logsLoopEnvios.Trim()) {
        $ultimaLinha = $logsLoopEnvios
        Write-Host "[loop-envios]" -ForegroundColor DarkCyan
        Write-Host $logsLoopEnvios -ForegroundColor Cyan
    }
}

Write-Host "`nTeste finalizado. Confere as mensagens trocadas no WhatsApp e o estado:" -ForegroundColor Magenta
Write-Host "  $backend/docs (login admin@ramotors.com / RAMotors2026! e olha em /conversas)" -ForegroundColor DarkGray
