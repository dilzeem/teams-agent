output "resource_group_name" {
  description = "The name of the created resource group."
  value       = azurerm_resource_group.main.name
}

output "app_service_plan_name" {
  description = "The name of the created App Service Plan."
  value       = azurerm_service_plan.main.name
}

output "app_service_name" {
  description = "The name of the created App Service."
  value       = azurerm_linux_web_app.main.name
}

output "app_service_default_hostname" {
  description = "The default hostname of the App Service."
  value       = azurerm_linux_web_app.main.default_hostname
}

output "app_service_principal_id" {
  description = "The Principal ID of the System Assigned Managed Identity for the App Service (if enabled)."
  value       = azurerm_linux_web_app.main.identity[0].principal_id # Access first identity block
  # This assumes SystemAssigned identity is used. If UserAssigned, structure changes.
  # Add a condition if identity might not be enabled or to handle different types.
  # Condition example: value = length(azurerm_linux_web_app.main.identity) > 0 ? azurerm_linux_web_app.main.identity[0].principal_id : "ManagedIdentityNotEnabled"
}
