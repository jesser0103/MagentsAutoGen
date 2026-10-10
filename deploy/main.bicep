@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Unique prefix/suffix for naming Azure resources')
param appNamePrefix string = 'magent'

@description('Azure OpenAI Endpoint')
@secure()
param azureOpenaiEndpoint string = ''

@description('Azure OpenAI API Key')
@secure()
param azureOpenaiApiKey string = ''

@description('Azure OpenAI Chat Deployment Name')
param azureOpenaiDeploymentName string = 'gpt-4o'

@description('Azure OpenAI Embedding Deployment Name')
param azureOpenaiEmbeddingDeployment string = 'text-embedding-3-small'

@description('Azure AI Content Safety Endpoint')
@secure()
param contentSafetyEndpoint string = ''

@description('Azure AI Content Safety Key')
@secure()
param contentSafetyKey string = ''

@description('Container Registry Server (e.g. myacr.azurecr.io or docker.io)')
param containerRegistryServer string

@description('Container Registry Username')
@secure()
param containerRegistryUsername string = ''

@description('Container Registry Password')
@secure()
param containerRegistryPassword string = ''

@description('Microsoft Entra ID Tenant ID for Corporate SSO (optional)')
param entraTenantId string = ''

@description('Microsoft Entra ID Client ID for Corporate SSO (optional)')
param entraClientId string = ''

@description('Microsoft Entra ID Client Secret for Corporate SSO (optional)')
@secure()
param entraClientSecret string = ''

@description('Image tag for all 3 images')
param imageTag string = 'latest'

@description('PostgreSQL administrator username')
param pgAdminUser string = 'magentadmin'

@description('PostgreSQL administrator password')
@secure()
param pgAdminPassword string

var uniqueSuffix = uniqueString(resourceGroup().id)
var logAnalyticsName = 'law-${appNamePrefix}-${uniqueSuffix}'
var appInsightsName = 'appi-${appNamePrefix}-${uniqueSuffix}'
var containerAppEnvName = 'cae-${appNamePrefix}-${uniqueSuffix}'
var pgServerName = 'psql-${appNamePrefix}-${uniqueSuffix}'
var storageName = 'st${appNamePrefix}${uniqueSuffix}'
var pgDatabaseName = 'magentdb'

var sandboxAppName = 'ca-sandbox'
var apiAppName = 'ca-api'
var frontendAppName = 'ca-frontend'

var apiImage = '${containerRegistryServer}/magent-autogen-api:${imageTag}'
var frontendImage = '${containerRegistryServer}/magent-autogen-frontend:${imageTag}'
var sandboxImage = '${containerRegistryServer}/magent-autogen-sandbox:${imageTag}'

// ── 1. Log Analytics & Application Insights ──────────────────────────────────
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

// ── 2. Azure Container Apps Managed Environment ──────────────────────────────
resource containerAppEnv 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: containerAppEnvName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

// ── 2b. Azure Database for PostgreSQL Flexible Server ─────────────────────────
resource pgServer 'Microsoft.DBforPostgreSQL/flexibleServers@2022-12-01' = {
  name: pgServerName
  location: location
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    version: '16'
    administratorLogin: pgAdminUser
    administratorLoginPassword: pgAdminPassword
    storage: {
      storageSizeGB: 32
    }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
  }
}

resource pgDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2022-12-01' = {
  parent: pgServer
  name: pgDatabaseName
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

// Allow Azure services to connect (for Container Apps)
resource pgFirewall 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2022-12-01' = {
  parent: pgServer
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

var databaseUrl = 'postgresql://${pgAdminUser}:${pgAdminPassword}@${pgServer.properties.fullyQualifiedDomainName}:5432/${pgDatabaseName}?sslmode=require'

// ── 2c. Azure Blob Storage Account ────────────────────────────────────────────
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageName
  location: location
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: 30
    }
    isVersioningEnabled: true
  }
}

resource artifactsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: 'artifacts'
  properties: {
    publicAccess: 'None'
  }
}

var storageConnectionString = 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount.listKeys().keys[0].value};EndpointSuffix=core.windows.net'

// Registry credentials configuration
var registries = !empty(containerRegistryUsername) ? [
  {
    server: containerRegistryServer
    username: containerRegistryUsername
    passwordSecretRef: 'registry-password'
  }
] : []

var registrySecrets = !empty(containerRegistryPassword) ? [
  {
    name: 'registry-password'
    value: containerRegistryPassword
  }
] : []

// ── 3. Sandbox Container App (Internal Only) ──────────────────────────────────
resource sandboxApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: sandboxAppName
  location: location
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      registries: registries
      secrets: registrySecrets
      ingress: {
        external: false
        targetPort: 8081
        transport: 'auto'
      }
    }
    template: {
      containers: [
        {
          name: 'sandbox'
          image: sandboxImage
          resources: {
            cpu: json('0.5')
            memory: '1.0Gi'
          }
          env: [
            {
              name: 'SANDBOX_VALIDATION_TIMEOUT_SECONDS'
              value: '60'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 3
      }
    }
  }
}

// ── 4. API Container App (Internal / External on port 8000) ───────────────────
resource apiApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: apiAppName
  location: location
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      registries: registries
      secrets: concat(registrySecrets, [
        {
          name: 'aoai-key'
          value: azureOpenaiApiKey
        }
        {
          name: 'cs-key'
          value: contentSafetyKey
        }
        {
          name: 'pg-password'
          value: pgAdminPassword
        }
        {
          name: 'database-url'
          value: databaseUrl
        }
        {
          name: 'storage-conn-str'
          value: storageConnectionString
        }
      ])
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        corsPolicy: {
          allowedOrigins: ['*']
          allowedMethods: ['GET', 'POST', 'OPTIONS']
          allowedHeaders: ['*']
        }
      }
    }
    template: {
      containers: [
        {
          name: 'api'
          image: apiImage
          resources: {
            cpu: json('0.75')
            memory: '1.5Gi'
          }
          env: [
            {
              name: 'MAGENT_PROVIDER'
              value: 'azure'
            }
            {
              name: 'AZURE_OPENAI_ENDPOINT'
              value: azureOpenaiEndpoint
            }
            {
              name: 'AZURE_OPENAI_API_KEY'
              secretRef: 'aoai-key'
            }
            {
              name: 'AZURE_OPENAI_DEPLOYMENT_NAME'
              value: azureOpenaiDeploymentName
            }
            {
              name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT'
              value: azureOpenaiEmbeddingDeployment
            }
            {
              name: 'CONTENT_SAFETY_ENDPOINT'
              value: contentSafetyEndpoint
            }
            {
              name: 'CONTENT_SAFETY_KEY'
              secretRef: 'cs-key'
            }
            {
              name: 'MAGENT_SANDBOX_URL'
              value: 'http://${sandboxAppName}:8081'
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              value: appInsights.properties.ConnectionString
            }
            {
              name: 'MAGENT_DATABASE_URL'
              secretRef: 'database-url'
            }
            {
              name: 'AZURE_STORAGE_CONNECTION_STRING'
              secretRef: 'storage-conn-str'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 5
      }
    }
  }
  depends_on: [
    sandboxApp
  ]
}

// ── 5. Next.js Frontend Container App (Public Entrypoint) ─────────────────────
resource frontendApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: frontendAppName
  location: location
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      registries: registries
      secrets: concat(registrySecrets, !empty(entraClientSecret) ? [
        {
          name: 'entra-client-secret'
          value: entraClientSecret
        }
      ] : [])
      ingress: {
        external: true
        targetPort: 3000
        transport: 'auto'
      }
    }
    template: {
      containers: [
        {
          name: 'frontend'
          image: frontendImage
          resources: {
            cpu: json('0.5')
            memory: '1.0Gi'
          }
          env: [
            {
              name: 'INTERNAL_API_URL'
              value: 'http://${apiAppName}:8000'
            }
            {
              name: 'NEXT_PUBLIC_PROVIDER_MODE'
              value: 'azure'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 5
      }
    }
  }
  depends_on: [
    apiApp
  ]
}

// ── 6. Microsoft Entra ID EasyAuth (Optional Corporate SSO) ───────────────────
resource frontendAuthConfig 'Microsoft.App/containerApps/authConfigs@2023-05-01' = if (!empty(entraClientId)) {
  parent: frontendApp
  name: 'current'
  properties: {
    platform: {
      enabled: true
    }
    globalValidation: {
      unauthenticatedClientAction: 'RedirectToLoginPage'
      redirectToProvider: 'azureActiveDirectory'
    }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        registration: {
          clientId: entraClientId
          clientSecretSettingName: 'entra-client-secret'
          openIdIssuer: 'https://login.microsoftonline.com/${entraTenantId}/v2.0'
        }
      }
    }
  }
}

// ── Outputs ───────────────────────────────────────────────────────────────────
output frontendUrl string = 'https://${frontendApp.properties.configuration.ingress.fqdn}'
output apiUrl string = 'https://${apiApp.properties.configuration.ingress.fqdn}'
output sandboxInternalFqdn string = sandboxApp.properties.configuration.ingress.fqdn
output postgresHost string = pgServer.properties.fullyQualifiedDomainName
output postgresDatabaseName string = pgDatabaseName
output storageAccountName string = storageAccount.name
output blobContainerName string = 'artifacts'
