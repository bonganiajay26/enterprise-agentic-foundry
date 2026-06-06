output "aks_cluster_name" {
  description = "AKS cluster name"
  value       = azurerm_kubernetes_cluster.platform.name
}

output "aks_cluster_id" {
  description = "AKS cluster resource ID"
  value       = azurerm_kubernetes_cluster.platform.id
}

output "aks_kube_config" {
  description = "AKS kubeconfig (base64)"
  value       = azurerm_kubernetes_cluster.platform.kube_config_raw
  sensitive   = true
}

output "aks_oidc_issuer_url" {
  description = "OIDC issuer URL for workload identity federation"
  value       = azurerm_kubernetes_cluster.platform.oidc_issuer_url
}

output "acr_login_server" {
  description = "ACR login server URL"
  value       = azurerm_container_registry.platform.login_server
}

output "acr_id" {
  description = "ACR resource ID"
  value       = azurerm_container_registry.platform.id
}

output "key_vault_uri" {
  description = "Key Vault URI"
  value       = azurerm_key_vault.platform.vault_uri
}

output "key_vault_id" {
  description = "Key Vault resource ID"
  value       = azurerm_key_vault.platform.id
}

output "log_analytics_workspace_id" {
  description = "Log Analytics workspace ID"
  value       = azurerm_log_analytics_workspace.platform.id
}

output "vnet_id" {
  description = "Virtual network resource ID"
  value       = azurerm_virtual_network.platform.id
}

output "resource_group_name" {
  description = "Resource group name"
  value       = azurerm_resource_group.platform.name
}

output "kubelet_identity_object_id" {
  description = "Kubelet managed identity object ID (for RBAC)"
  value       = azurerm_kubernetes_cluster.platform.kubelet_identity[0].object_id
}
