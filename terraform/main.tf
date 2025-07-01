# Configure the Azure Provider
terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
  required_version = ">= 1.0"
}

provider "azurerm" {
  features {}
}

# Create a Resource Group
resource "azurerm_resource_group" "main" {
  name     = var.resource_group_name
  location = var.location
  tags     = var.tags
}

# Create an App Service Plan
resource "azurerm_service_plan" "main" { # Changed from azurerm_app_service_plan to azurerm_service_plan
  name                = var.app_service_plan_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  os_type             = "Linux" # Changed from kind = "Linux" and reserved = true
  sku_name            = var.app_service_plan_sku # Changed from sku { tier = "Basic", size = "B1" }
  tags                = var.tags
}

# Create an Azure App Service
resource "azurerm_linux_web_app" "main" { # Changed from azurerm_app_service to azurerm_linux_web_app
  name                = var.app_service_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  service_plan_id     = azurerm_service_plan.main.id # Changed from app_service_plan_id

  site_config {
    python_version = var.python_version # Changed from linux_fx_version = "PYTHON|3.10"
    # The 'azurerm_linux_web_app' resource uses 'python_version' directly.
    # Common settings like 'always_on' can be added here if needed (depends on SKU)
    # always_on = var.app_service_plan_sku == "B1" || var.app_service_plan_sku == "S1" ? true : false
  }

  app_settings = { # Merged app_settings from README example
    "ENVIRONMENT"        = "Production"
    "WEBSITE_RUN_FROM_PACKAGE" = "1" # Recommended for Azure App Service to improve deployment reliability
    # Add other app settings as needed from .env.example, to be configured in Azure Portal or via TF variables
    "CLIENT_ID"          = var.azure_ad_client_id
    "CLIENT_SECRET"      = var.azure_ad_client_secret # Note: Store actual secrets in Key Vault or secure pipeline variables
    "TENANT_ID"          = var.azure_ad_tenant_id
    "APP_REDIRECT_PATH"  = var.app_redirect_path
    "GRAPH_SCOPES"       = var.graph_scopes
    # "OAUTHLIB_INSECURE_TRANSPORT" = "0" # Should be off for production
  }

  identity {
    type = "SystemAssigned" # Example: enable System Assigned Managed Identity
  }

  tags = var.tags
}
