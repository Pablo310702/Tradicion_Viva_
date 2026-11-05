param(
    [string]$SshKey = $env:TRADICION_VIVA_SSH_KEY
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($SshKey)) {
    throw 'Define TRADICION_VIVA_SSH_KEY o ejecuta el script con -SshKey apuntando a la llave SSH.'
}

$sshKey = $SshKey
$tokenFile = Join-Path $PSScriptRoot '.whatsapp_access_token'
if (!(Test-Path $sshKey)) { throw "No existe la llave SSH: $sshKey" }
if (!(Test-Path $tokenFile)) { throw 'Crea .whatsapp_access_token en el proyecto y pega allí el token de Meta. No lo pegues en el chat.' }

$token = (Get-Content -Raw $tokenFile).Trim()
if ([string]::IsNullOrWhiteSpace($token)) { throw '.whatsapp_access_token está vacío.' }
$encodedToken = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($token))

ssh -i $sshKey opc@140.84.167.49 "echo $encodedToken | base64 -d > /home/opc/tradicion-viva/.whatsapp_access_token && chmod 600 /home/opc/tradicion-viva/.whatsapp_access_token"

$remoteScript = @'
from pathlib import Path
import re

env = Path('/home/opc/tradicion-viva/.env.production')
token = Path('/home/opc/tradicion-viva/.whatsapp_access_token').read_text().strip()
lines = []
for line in env.read_text().splitlines():
    value = line.strip()
    if not value or value.startswith('#') or re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', value):
        lines.append(line)

text = '\n'.join(lines)
values = {
    'WHATSAPP_GRAPH_API_VERSION': 'v25.0',
    'WHATSAPP_ACCESS_TOKEN': token,
    'WHATSAPP_PHONE_NUMBER_ID': '1379367871930009',
    'WHATSAPP_DEFAULT_TEMPLATE_NAME': 'tradicion_viva_comunicado',
    'WHATSAPP_DEFAULT_TEMPLATE_LANGUAGE': 'es_MX',
    'WHATSAPP_RECEIPT_TEMPLATE_NAME': 'comprobante_registro',
    'WHATSAPP_RECEIPT_TEMPLATE_LANGUAGE': 'es_MX',
}
for name, value in values.items():
    pattern = re.compile(r'(?m)^' + re.escape(name) + r'=.*$')
    replacement = name + '=' + value
    if pattern.search(text):
        text = pattern.sub(lambda _: replacement, text)
    else:
        text += '\n' + replacement

env.write_text(text.rstrip() + '\n')
env.chmod(0o600)
Path('/home/opc/tradicion-viva/.whatsapp_access_token').unlink(missing_ok=True)
print('whatsapp_configured')
'@

$encodedScript = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($remoteScript))
ssh -i $sshKey opc@140.84.167.49 "echo $encodedScript | base64 -d | python3"

ssh -i $sshKey opc@140.84.167.49 "cd /home/opc/tradicion-viva && docker compose -f docker-compose.production.yml up -d --force-recreate web"

$safeCheck = @'
import os
print('whatsapp_token_length=' + str(len(os.environ.get('WHATSAPP_ACCESS_TOKEN', ''))))
print('whatsapp_phone_number_id=' + os.environ.get('WHATSAPP_PHONE_NUMBER_ID', ''))
print('whatsapp_template=' + os.environ.get('WHATSAPP_DEFAULT_TEMPLATE_NAME', ''))
print('whatsapp_template_language=' + os.environ.get('WHATSAPP_DEFAULT_TEMPLATE_LANGUAGE', ''))
'@
$encodedCheck = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($safeCheck))
ssh -i $sshKey opc@140.84.167.49 "echo $encodedCheck | base64 -d | docker compose -f /home/opc/tradicion-viva/docker-compose.production.yml exec -T web python"
