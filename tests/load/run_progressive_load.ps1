param(
    [Parameter(Mandatory = $true)]
    [uri]$BaseUrl,
    [ValidateSet('step2', 'staged', 'stress')]
    [string]$Profile = 'step2',
    [switch]$RunAll
)

$productionHosts = @('tradicionviva.com.gt', 'www.tradicionviva.com.gt')
if ($productionHosts -contains $BaseUrl.Host.ToLowerInvariant()) {
    throw 'Por seguridad, este lanzador no permite pruebas de carga contra produccion. Usa un staging separado.'
}

if (-not (Get-Command k6 -ErrorAction SilentlyContinue)) {
    throw 'k6 no esta instalado o no esta disponible en PATH. Instala k6 antes de ejecutar la prueba.'
}

$profiles = if ($RunAll) { @('step2', 'staged', 'stress') } else { @($Profile) }
foreach ($selectedProfile in $profiles) {
    Write-Host "Iniciando perfil $selectedProfile contra $BaseUrl" -ForegroundColor Cyan
    $env:BASE_URL = $BaseUrl.AbsoluteUri.TrimEnd('/')
    $env:LOAD_PROFILE = $selectedProfile
    & k6 run tests/load/tradicion_viva.k6.js
    if ($LASTEXITCODE -ne 0) {
        throw "El perfil $selectedProfile no paso los umbrales. Se detiene la progresion."
    }
    Write-Host "Perfil $selectedProfile aprobado." -ForegroundColor Green
}
