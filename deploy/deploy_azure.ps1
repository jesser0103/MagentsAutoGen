# ==============================================================================
# MagentAutoGen — Automated Azure Container Apps Deployment Script (PowerShell)
# ==============================================================================

param (
    [string]$ResourceGroupName = "jassersouissi",
    [string]$Location = "eastus",
    [string]$AcrName = "",
    [string]$ImageTag = "latest"
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "[DEPLOY] MagentAutoGen -- Azure Container Apps (ACA)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Load .env file
if (Test-Path ".env") {
    Write-Host "[INFO] Loading credentials from .env..." -ForegroundColor Green
    Get-Content ".env" | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $parts = $line.Split("=", 2)
            $name = $parts[0].Trim()
            $value = $parts[1].Trim()
            [System.Environment]::SetEnvironmentVariable($name, $value, [System.EnvironmentVariableTarget]::Process)
        }
    }
} else {
    Write-Warning ".env file not found. Ensure Azure environment variables are set."
}

# 2. Check Azure CLI installation
Write-Host "[INFO] Checking Azure CLI installation..." -ForegroundColor Green
$azCmd = Get-Command az -ErrorAction SilentlyContinue
if (-not $azCmd) {
    Write-Host "[ERROR] Azure CLI (az) is not installed on this system." -ForegroundColor Red
    Write-Host "[INFO] To install Azure CLI automatically, run:" -ForegroundColor Yellow
    Write-Host "       Invoke-WebRequest -Uri https://aka.ms/installazurecliwindows -OutFile .\AzureCLI.msi; Start-Process msiexec.exe -Wait -ArgumentList '/I AzureCLI.msi /quiet'" -ForegroundColor Cyan
    Write-Host "[INFO] Or download the installer directly: https://aka.ms/installazurecliwindows" -ForegroundColor Yellow
    exit 1
}

Write-Host "[INFO] Checking Azure authentication..." -ForegroundColor Green
$account = az account show 2>$null | ConvertFrom-Json
if (-not $account) {
    Write-Host "[AUTH] Please login to Azure via az login..." -ForegroundColor Yellow
    az login
}

# 3. Create or ensure Resource Group
Write-Host "[INFO] Ensuring Resource Group '$ResourceGroupName' in '$Location'..." -ForegroundColor Green
az group create --name $ResourceGroupName --location $Location --output table

# 4. Create or locate ACR
if (-not $AcrName) {
    $subId = (az account show --query id -o tsv).Substring(0, 6)
    $AcrName = "acrmagent$subId"
}
Write-Host "[INFO] Ensuring Azure Container Registry '$AcrName'..." -ForegroundColor Green
az acr create --resource-group $ResourceGroupName --name $AcrName --sku Basic --admin-enabled true --output table

$acrServer = "$AcrName.azurecr.io"
$acrCreds = az acr credential show --name $AcrName | ConvertFrom-Json
$acrUser = $acrCreds.username
$acrPassword = $acrCreds.passwords[0].value

# 5. Log in to ACR
Write-Host "[AUTH] Logging in to ACR $acrServer..." -ForegroundColor Green
docker login $acrServer -u $acrUser -p $acrPassword

# 6. Build and Tag Images
Write-Host "[BUILD] Building and tagging Docker images..." -ForegroundColor Green

Write-Host "--> Building magent-autogen-sandbox..." -ForegroundColor Cyan
docker build -t "$acrServer/magent-autogen-sandbox:$ImageTag" -f docker/Dockerfile.sandbox .

Write-Host "--> Building magent-autogen-api..." -ForegroundColor Cyan
docker build -t "$acrServer/magent-autogen-api:$ImageTag" -f docker/Dockerfile.api .

Write-Host "--> Building magent-autogen-frontend..." -ForegroundColor Cyan
docker build -t "$acrServer/magent-autogen-frontend:$ImageTag" -f frontend/Dockerfile ./frontend

# 7. Push Images to ACR
Write-Host "[PUSH] Pushing images to ACR..." -ForegroundColor Green
docker push "$acrServer/magent-autogen-sandbox:$ImageTag"
docker push "$acrServer/magent-autogen-api:$ImageTag"
docker push "$acrServer/magent-autogen-frontend:$ImageTag"

# 8. Deploy Bicep template
Write-Host "[DEPLOY] Deploying Bicep template (ACA Environment + Microservices + PostgreSQL + Blob)..." -ForegroundColor Green

$aoaiEndpoint = [System.Environment]::GetEnvironmentVariable("AZURE_OPENAI_ENDPOINT")
$aoaiKey = [System.Environment]::GetEnvironmentVariable("AZURE_OPENAI_API_KEY")
$aoaiDeploy = [System.Environment]::GetEnvironmentVariable("AZURE_OPENAI_DEPLOYMENT_NAME")
$aoaiEmbed = [System.Environment]::GetEnvironmentVariable("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
$csEndpoint = [System.Environment]::GetEnvironmentVariable("CONTENT_SAFETY_ENDPOINT")
$csKey = [System.Environment]::GetEnvironmentVariable("CONTENT_SAFETY_KEY")
$pgPassword = [System.Environment]::GetEnvironmentVariable("PG_ADMIN_PASSWORD")
if (-not $pgPassword) {
    $pgPassword = "MagentAdmin!" + (-join ((65..90) + (97..122) + (48..57) | Get-Random -Count 16 | ForEach-Object {[char]$_}))
}

$deployment = az deployment group create `
    --resource-group $ResourceGroupName `
    --template-file deploy/main.bicep `
    --parameters `
        containerRegistryServer=$acrServer `
        containerRegistryUsername=$acrUser `
        containerRegistryPassword=$acrPassword `
        imageTag=$ImageTag `
        azureOpenaiEndpoint=$aoaiEndpoint `
        azureOpenaiApiKey=$aoaiKey `
        azureOpenaiDeploymentName=$aoaiDeploy `
        azureOpenaiEmbeddingDeployment=$aoaiEmbed `
        contentSafetyEndpoint=$csEndpoint `
        contentSafetyKey=$csKey `
        pgAdminPassword=$pgPassword `
    --output json | ConvertFrom-Json

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "[SUCCESS] DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "Frontend URL          : $($deployment.properties.outputs.frontendUrl.value)" -ForegroundColor Yellow
Write-Host "Backend API URL       : $($deployment.properties.outputs.apiUrl.value)" -ForegroundColor Yellow
Write-Host "Sandbox Internal Host : $($deployment.properties.outputs.sandboxInternalFqdn.value)" -ForegroundColor Cyan
Write-Host "PostgreSQL Host       : $($deployment.properties.outputs.postgresHost.value)" -ForegroundColor Cyan
Write-Host "Storage Account       : $($deployment.properties.outputs.storageAccountName.value)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Green
