// Azure Bicep — AKS Platform Landing Zone
// Equivalent to terraform/azure/main.tf but using native Azure Bicep

targetScope = 'subscription'

@description('Naming prefix for all resources')
param prefix string = 'platform'

@description('Target environment')
@allowed(['dev', 'staging', 'production'])
param environment string

@description('Primary Azure region')
param location string = 'eastus2'

@description('DR Azure region')
param drLocation string = 'westus2'

@description('Kubernetes version')
param kubernetesVersion string = '1.28'

@description('System node pool VM size')
param systemNodeVmSize string = 'Standard_D2s_v5'

@description('Workload node pool VM size')
param workloadNodeVmSize string = 'Standard_D4s_v5'

@description('AKS admin group object IDs')
param aksAdminGroupIds array = []

@description('Tags to apply to all resources')
param tags object = {
  Environment: environment
  ManagedBy: 'Bicep'
  Project: prefix
}

// ─── Resource Group ───────────────────────────────────────────────────
resource rg 'Microsoft.Resources/resourceGroups@2023-07-01' = {
  name: '${prefix}-${environment}-rg'
  location: location
  tags: tags
}

// ─── VNet Module ──────────────────────────────────────────────────────
module vnet 'modules/vnet.bicep' = {
  name: 'vnet-deployment'
  scope: rg
  params: {
    prefix: prefix
    environment: environment
    location: location
    tags: tags
  }
}

// ─── Key Vault Module ─────────────────────────────────────────────────
module keyVault 'modules/keyvault.bicep' = {
  name: 'keyvault-deployment'
  scope: rg
  params: {
    prefix: prefix
    environment: environment
    location: location
    tags: tags
  }
}

// ─── Container Registry Module ────────────────────────────────────────
module acr 'modules/acr.bicep' = {
  name: 'acr-deployment'
  scope: rg
  params: {
    prefix: prefix
    environment: environment
    location: location
    drLocation: drLocation
    tags: tags
  }
}

// ─── Log Analytics Module ─────────────────────────────────────────────
module logAnalytics 'modules/log-analytics.bicep' = {
  name: 'law-deployment'
  scope: rg
  params: {
    prefix: prefix
    environment: environment
    location: location
    tags: tags
  }
}

// ─── AKS Module ───────────────────────────────────────────────────────
module aks 'modules/aks.bicep' = {
  name: 'aks-deployment'
  scope: rg
  params: {
    prefix: prefix
    environment: environment
    location: location
    kubernetesVersion: kubernetesVersion
    systemNodeVmSize: systemNodeVmSize
    workloadNodeVmSize: workloadNodeVmSize
    aksAdminGroupIds: aksAdminGroupIds
    nodesSubnetId: vnet.outputs.aksNodesSubnetId
    podsSubnetId: vnet.outputs.aksPodsSubnetId
    logAnalyticsWorkspaceId: logAnalytics.outputs.workspaceId
    tags: tags
  }
}

// ─── RBAC: AKS → ACR ──────────────────────────────────────────────────
resource acrPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acr.outputs.acrId, aks.outputs.kubeletIdentityObjectId, 'AcrPull')
  properties: {
    principalId: aks.outputs.kubeletIdentityObjectId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d') // AcrPull
    principalType: 'ServicePrincipal'
  }
}

// ─── Outputs ──────────────────────────────────────────────────────────
output aksClusterName string = aks.outputs.clusterName
output acrLoginServer string = acr.outputs.loginServer
output keyVaultUri string = keyVault.outputs.vaultUri
output resourceGroupName string = rg.name
