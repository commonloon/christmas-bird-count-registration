# Powershell script to set up oauth in google cloud
$json = Get-Content client_secret.json | ConvertFrom-Json
$clientId = $json.web.client_id
$clientSecret = $json.web.client_secret

$bytes = New-Object byte[] 32
[System.Security.Cryptography.RNGCryptoServiceProvider]::Create().GetBytes($bytes)
$flaskSecret = [Convert]::ToBase64String($bytes)

$clientId | gcloud secrets create google-oauth-client-id --data-file=-
$clientSecret | gcloud secrets create google-oauth-client-secret --data-file=-
$flaskSecret | gcloud secrets create flask-secret-key --data-file=-

$projectId = gcloud config get-value project
$projectNumber = gcloud projects describe $projectId --format="value(projectNumber)"
gcloud projects add-iam-policy-binding $projectId --member="serviceAccount:$projectNumber-compute@developer.gserviceaccount.com" --role="roles/secretmanager.secretAccessor"