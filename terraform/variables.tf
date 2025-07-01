variable "resource_group_name" {
  description = "The name of the Azure Resource Group."
  type        = string
  default     = "teams-agent-rg"
}

variable "location" {
  description = "The Azure region where resources will be created."
  type        = string
  default     = "WestEurope"
}

variable "app_service_plan_name" {
  description = "The name of the Azure App Service Plan."
  type        = string
  default     = "teams-agent-asp"
}

variable "app_service_plan_sku" {
  description = "The SKU for the App Service Plan (e.g., B1, S1, P1V2)."
  type        = string
  default     = "B1" # Basic tier, good for dev/test
}

variable "app_service_name" {
  description = "The name of the Azure App Service. This will be part of the URL (e.g., <name>.azurewebsites.net)."
  type        = string
  default     = "teams-agent-app-py" # Needs to be globally unique
}

variable "python_version" {
  description = "The Python version for the App Service."
  type        = string
  default     = "3.10"
}

variable "tags" {
  description = "A map of tags to assign to the resources."
  type        = map(string)
  default = {
    project = "TeamsAgentPython"
    environment = "Dev"
  }
}

# Variables for App Settings (from .env.example)
# These should ideally be populated from a secure source like Azure Key Vault or pipeline variables for production.
variable "azure_ad_client_id" {
  description = "Azure AD Application Client ID."
  type        = string
  sensitive   = true # Mark as sensitive, though actual value should come from secure source
}

variable "azure_ad_client_secret" {
  description = "Azure AD Application Client Secret."
  type        = string
  sensitive   = true # Mark as sensitive
}

variable "azure_ad_tenant_id" {
  description = "Azure AD Tenant ID."
  type        = string
  sensitive   = true
}

variable "app_redirect_path" {
  description = "Application redirect path for OAuth."
  type        = string
  default     = "/getAToken"
}

variable "graph_scopes" {
  description = "Space-separated string of Graph API scopes."
  type        = string
  default     = "User.Read Chat.ReadWrite"
}
