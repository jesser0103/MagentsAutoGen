#!/usr/bin/env bash
# ==============================================================================
# MagentAutoGen — Automated Azure Container Apps Deployment Script (Bash)
# ==============================================================================

set -euo pipefail

RESOURCE_GROUP="${1:-jassersouissi}"
LOCATION="${2:-eastus}"
IMAGE_TAG="${3:-latest}"

echo "=========================================================="
echo "🚀 MagentAutoGen — Deploying to Azure Container Apps (ACA)"
echo "=========================================================="

# 1. Load .env
if [ -f ".env" ]; then
    echo "📄 Loading .env..."
    export $(grep -v '^#' .env | xargs)
fi

# 2. Check Azure CLI
az account show > /dev/null 2>&1 || az login

# 3. Create Resource Group
echo "📦 Ensuring Resource Group '$RESOURCE_GROUP' in '$LOCATION'..."
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" -o table

# 4. Create ACR
SUB_ID=$(az account show --query id -o tsv | cut -c1-6)
ACR_NAME="acrmagent${SUB_ID}"
echo "📦 Ensuring ACR '$ACR_NAME'..."
az acr create --resource-group "$RESOURCE_GROUP" --name "$ACR_NAME" --sku Basic --admin-enabled true -o table

ACR_SERVER="${ACR_NAME}.azurecr.io"
ACR_USER=$(az acr credential show --name "$ACR_NAME" --query username -o tsv)
ACR_PASS=$(az acr credential show --name "$ACR_NAME" --query "passwords[0].value" -o tsv)

# 5. Login to ACR
echo "🔐 Logging in to ACR..."
echo "$ACR_PASS" | docker login "$ACR_SERVER" -u "$ACR_USER" --password-stdin

# 6. Build and Tag Images
echo "🔨 Building images..."
docker build -t "$ACR_SERVER/magent-autogen-sandbox:$IMAGE_TAG" -f docker/Dockerfile.sandbox .
docker build -t "$ACR_SERVER/magent-autogen-api:$IMAGE_TAG" -f docker/Dockerfile.api .
docker build -t "$ACR_SERVER/magent-autogen-frontend:$IMAGE_TAG" -f frontend/Dockerfile ./frontend

# 7. Push Images
echo "📤 Pushing images..."
docker push "$ACR_SERVER/magent-autogen-sandbox:$IMAGE_TAG"
docker push "$ACR_SERVER/magent-autogen-api:$IMAGE_TAG"
docker push "$ACR_SERVER/magent-autogen-frontend:$IMAGE_TAG"

# 8. Deploy Bicep
echo "🚀 Deploying Bicep template..."
PG_PASS="${PG_ADMIN_PASSWORD:-MagentAdmin!$(openssl rand -hex 8)}"
az deployment group create \
    --resource-group "$RESOURCE_GROUP" \
    --template-file deploy/main.bicep \
    --parameters \
        containerRegistryServer="$ACR_SERVER" \
        containerRegistryUsername="$ACR_USER" \
        containerRegistryPassword="$ACR_PASS" \
        imageTag="$IMAGE_TAG" \
        azureOpenaiEndpoint="${AZURE_OPENAI_ENDPOINT:-}" \
        azureOpenaiApiKey="${AZURE_OPENAI_API_KEY:-}" \
        azureOpenaiDeploymentName="${AZURE_OPENAI_DEPLOYMENT_NAME:-gpt-4o}" \
        azureOpenaiEmbeddingDeployment="${AZURE_OPENAI_EMBEDDING_DEPLOYMENT:-text-embedding-3-small}" \
        contentSafetyEndpoint="${CONTENT_SAFETY_ENDPOINT:-}" \
        contentSafetyKey="${CONTENT_SAFETY_KEY:-}" \
        pgAdminPassword="$PG_PASS" \
    -o table

echo "=========================================================="
echo "🎉 DEPLOYMENT COMPLETE!"
echo "=========================================================="
