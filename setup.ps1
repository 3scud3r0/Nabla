param([switch]$WithLatex)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$pythonCommand = Get-Command py -ErrorAction SilentlyContinue
if ($pythonCommand) {
    $python = 'py'
    $arguments = @('-3')
} else {
    $python = 'python'
    $arguments = @()
}
& $python @arguments --version
if ($LASTEXITCODE -ne 0) { throw 'Python 3.10+ não foi encontrado.' }
& $python @arguments -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Falha ao criar ambiente virtual.' }
& .\.venv\Scripts\python.exe -m pip install -e .
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar NablaMath.' }
& .\.venv\Scripts\nabla.exe doctor
if ($LASTEXITCODE -ne 0) { throw 'Ambiente fora do contrato suportado; veja o diagnóstico acima.' }
if ($WithLatex -and -not (Get-Command pdflatex -ErrorAction SilentlyContinue)) {
    Write-Warning 'Instale uma distribuição TeX para gerar PDF; arquivos .tex funcionam sem ela.'
}
Write-Host 'Pronto. Execute .\.venv\Scripts\nabla.exe run "(x+x)/x" --value x=3'
