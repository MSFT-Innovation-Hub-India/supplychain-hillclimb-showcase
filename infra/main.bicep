targetScope = 'resourceGroup'

@description('Azure region of the existing Container Apps environment.')
param location string = 'swedencentral'

@description('Name of the Container App to create or update.')
param containerAppName string = 'foundry-agent-grader-app'

@description('Name of the existing Container Apps environment.')
param containerAppsEnvironmentName string = 'cae-foundry-agent-grader'

@description('Name of the existing Azure Container Registry.')
param containerRegistryName string = 'foundrygradermcp35d56b'

@description('Container image. Use a public bootstrap image for the first RBAC deployment, then the ACR image.')
param containerImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

@description('Use the public image settings while managed-identity RBAC propagates.')
param bootstrapMode bool = true

@description('Resource group containing the existing Foundry project.')
param foundryResourceGroupName string = 'rg-foundry-projects'

@description('Existing Foundry account name.')
param foundryAccountName string = 'viarbat-foundry-projects'

@description('Existing Foundry project name.')
param foundryProjectName string = 'rft-models-hosting-project'

@description('Existing Foundry project endpoint used by the app.')
param foundryProjectEndpoint string = 'https://viarbat-foundry-projects.services.ai.azure.com/api/projects/rft-models-hosting-project'

@description('Pinned version of the SFT agent. Change via az containerapp update --set-env-vars, no rebuild needed.')
param sftAgentVersion string = '14'

@description('Pinned version of the RFT agent. Change via az containerapp update --set-env-vars, no rebuild needed.')
param rftAgentVersion string = '13'

@description('Pinned version of the Teacher agent. Change via az containerapp update --set-env-vars, no rebuild needed.')
param teacherAgentVersion string = '2'

var acrPullRoleDefinitionId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
var foundryAgentConsumerRoleDefinitionId = 'eed3b665-ab3a-47b6-8f48-c9382fb1dad6'
var targetPort = bootstrapMode ? 80 : 8501
var productionProbes = [
  {
    type: 'Liveness'
    httpGet: {
      path: '/_stcore/health'
      port: 8501
      scheme: 'HTTP'
    }
    initialDelaySeconds: 20
    periodSeconds: 30
    timeoutSeconds: 5
    failureThreshold: 3
  }
  {
    type: 'Readiness'
    httpGet: {
      path: '/_stcore/health'
      port: 8501
      scheme: 'HTTP'
    }
    initialDelaySeconds: 10
    periodSeconds: 10
    timeoutSeconds: 5
    failureThreshold: 3
  }
]

resource managedEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  name: containerAppsEnvironmentName
}

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: containerRegistryName
}

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: containerAppName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: managedEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: targetPort
        transport: 'auto'
        allowInsecure: false
      }
      registries: bootstrapMode ? [] : [
        {
          server: containerRegistry.properties.loginServer
          identity: 'system'
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'model-comparison-app'
          image: containerImage
          env: [
            {
              name: 'AZURE_AI_PROJECT_ENDPOINT'
              value: foundryProjectEndpoint
            }
            {
              name: 'SFT_AGENT_NAME'
              value: 'SupplyChainOrderFulfilmentAgent-SFT'
            }
            {
              name: 'SFT_AGENT_VERSION'
              value: sftAgentVersion
            }
            {
              name: 'RFT_AGENT_NAME'
              value: 'SupplyChainOrderFulfilmentAgent-RFT'
            }
            {
              name: 'RFT_AGENT_VERSION'
              value: rftAgentVersion
            }
            {
              name: 'TEACHER_AGENT_NAME'
              value: 'SupplyChainOrderFulfilmentAgent-Teacher'
            }
            {
              name: 'TEACHER_AGENT_VERSION'
              value: teacherAgentVersion
            }
            {
              name: 'AZURE_TOKEN_CREDENTIALS'
              value: 'ManagedIdentityCredential'
            }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          probes: bootstrapMode ? [] : productionProbes
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 2
      }
    }
  }
}

resource acrPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerRegistry.id, containerApp.id, acrPullRoleDefinitionId)
  scope: containerRegistry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleDefinitionId)
    principalId: containerApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

module foundryAgentConsumerRole 'foundry-role.bicep' = {
  name: 'foundry-agent-consumer-role'
  scope: resourceGroup(subscription().subscriptionId, foundryResourceGroupName)
  params: {
    accountName: foundryAccountName
    projectName: foundryProjectName
    principalId: containerApp.identity.principalId
    roleDefinitionId: foundryAgentConsumerRoleDefinitionId
  }
}

output containerAppId string = containerApp.id
output containerAppPrincipalId string = containerApp.identity.principalId
output containerAppFqdn string = containerApp.properties.configuration.ingress.fqdn
output managedEnvironmentId string = managedEnvironment.id
output containerRegistryId string = containerRegistry.id
