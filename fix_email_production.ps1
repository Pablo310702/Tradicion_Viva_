$ErrorActionPreference = 'Stop'

$sshKey = Join-Path $PSScriptRoot 'Desktop\PG I Y II\ssh-key-2026-10-27.key'
if (!(Test-Path $sshKey)) {
    $sshKey = 'C:\Users\Pablo Alvarez\Desktop\PG I Y II\ssh-key-2026-10-27.key'
}
$passwordFile = Join-Path $PSScriptRoot '.smtp_app_password'
if (!(Test-Path $passwordFile)) { throw 'No existe .smtp_app_password en el proyecto.' }

$password = (Get-Content -Raw $passwordFile).Trim()
$encodedPassword = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($password))

ssh -i $sshKey opc@140.84.167.49 "echo $encodedPassword | base64 -d > /home/opc/tradicion-viva/.gmail_app_password && chmod 600 /home/opc/tradicion-viva/.gmail_app_password"

$remoteScript = @'
from pathlib import Path
import re

env = Path('/home/opc/tradicion-viva/.env.production')
password = Path('/home/opc/tradicion-viva/.gmail_app_password').read_text().strip()
lines = []
for line in env.read_text().splitlines():
    value = line.strip()
    if not value or value.startswith('#') or re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', value):
        lines.append(line)

values = {
    'EMAIL_BACKEND': 'django.core.mail.backends.smtp.EmailBackend',
    'EMAIL_HOST': 'smtp.gmail.com',
    'EMAIL_PORT': '587',
    'EMAIL_USE_TLS': 'True',
    'EMAIL_USE_SSL': 'False',
    'EMAIL_HOST_USER': 'tradicionvivagt@gmail.com',
    'EMAIL_HOST_PASSWORD': password,
    'DEFAULT_FROM_EMAIL': 'TRADICIÓN VIVA <tradicionvivagt@gmail.com>',
}

text = '\n'.join(lines)
for name, value in values.items():
    pattern = re.compile(r'(?m)^' + re.escape(name) + r'=.*$')
    replacement = name + '=' + value
    if pattern.search(text):
        text = pattern.sub(lambda _: replacement, text)
    else:
        text += '\n' + replacement

env.write_text(text.rstrip() + '\n')
env.chmod(0o600)
Path('/home/opc/tradicion-viva/.gmail_app_password').unlink(missing_ok=True)
print('gmail_configured')
'@

$encodedScript = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($remoteScript))
ssh -i $sshKey opc@140.84.167.49 "echo $encodedScript | base64 -d | python3"

ssh -i $sshKey opc@140.84.167.49 "cd /home/opc/tradicion-viva && docker compose -f docker-compose.production.yml up -d --force-recreate web"

$testScript = @'
import os, smtplib
with smtplib.SMTP(os.environ['EMAIL_HOST'], int(os.environ['EMAIL_PORT']), timeout=20) as smtp:
    smtp.starttls()
    smtp.login(os.environ['EMAIL_HOST_USER'], os.environ['EMAIL_HOST_PASSWORD'])
print('gmail_smtp_ok')
'@
$encodedTest = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($testScript))
ssh -i $sshKey opc@140.84.167.49 "echo $encodedTest | base64 -d | docker compose -f /home/opc/tradicion-viva/docker-compose.production.yml exec -T web python"
