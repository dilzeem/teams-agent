# Microsoft Teams Agent with `Agents-for-python`

This project demonstrates how to build and deploy a **bare-minimum Microsoft Teams agent** using the [`microsoft/Agents-for-python`](https://github.com/microsoft/Agents-for-python) SDK. The agent is designed to run as a simple Python web service, leverage **delegated user permissions** (not a global service principal), and be deployed to **Azure App Service** using **GitHub Actions**. All dependencies and environments are managed with [`uv`](https://github.com/astral-sh/uv).

---

## Table of Contents

- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Setup & Development](#setup--development)
- [Managing Dependencies with uv](#managing-dependencies-with-uv)
- [Teams Agent: Delegated Permissions](#teams-agent-delegated-permissions)
- [Terraform: Azure Infrastructure](#terraform-azure-infrastructure)
- [Deployment: Azure App Service & GitHub Actions](#deployment-azure-app-service--github-actions)
- [Security Notes](#security-notes)
- [References](#references)

---

## Project Structure

| Folder/File        | Purpose                                              |
|--------------------|------------------------------------------------------|
| `app/`             | Python source code for the Teams agent               |
| `pyproject.toml`   | Python project metadata and dependencies             |
| `requirements.txt` | (Optional) For uv compatibility                      |
| `.env`             | Environment variables (never commit secrets)         |
| `terraform/`       | Terraform IaC for Azure resources                    |
| `.github/workflows/azure-appservice.yml` | GitHub Actions workflow for CI/CD |
| `README.md`        | Project documentation (this file)                    |

---

## Prerequisites

- **Python 3.10+**
- **uv** for dependency and virtual environment management
- **Terraform** for Azure resource provisioning
- **Azure CLI** for authentication and local testing
- **Microsoft 365 developer account** with Teams access
- **Azure subscription** with permissions to create App Services
- **GitHub repository** for source and CI/CD

---

## Setup & Development

1. **Clone the repository:**
```

git clone https://github.com/your-org/your-repo.git
cd your-repo

```

2. **Install `uv` (if not already installed):**
```

pip install uv

```

3. **Install dependencies and create a virtual environment:**
```

uv venv
uv pip install -r requirements.txt

```

Or, if using `pyproject.toml`:
```

uv pip install .

```

4. **Run the agent locally:**
```

uv pip install -e .
uv python app/main.py

```

---

## Managing Dependencies with uv

- Add dependencies:
```

uv pip install <package>

```
- Update dependencies:
```

uv pip install --upgrade <package>

```
- Export requirements (for CI/CD):
```

uv pip freeze > requirements.txt

```

---

## Teams Agent: Delegated Permissions

- **Delegated permissions**: The agent should authenticate as the **signed-in user** (not a service principal), so actions are performed on behalf of the user, respecting their Teams/Microsoft 365 permissions.
- **OAuth2 Authorization Code Flow** is required; users must sign in and consent to the required scopes.
- **No global admin/service principal required**: This improves security and auditability.

**Key setup steps:**
- Register an Azure AD application for your agent.
- Configure **redirect URIs** for both local and deployed environments.
- Request only the minimal delegated permissions (e.g., `Chat.Read`, `User.Read`).
- Implement OAuth2 code flow in your agent (using `msal` or similar).

---

## Terraform: Azure Infrastructure

Use Terraform to provision:

- **Resource group**
- **App Service plan (Linux)**
- **Azure App Service** (Python runtime)
- **(Optional) Azure Key Vault** for secrets

**Example Terraform structure:**

```
resource "azurerm_resource_group" "main" {
name     = "teams-agent-rg"
location = "westeurope"
}

resource "azurerm_app_service_plan" "main" {
name                = "teams-agent-plan"
location            = azurerm_resource_group.main.location
resource_group_name = azurerm_resource_group.main.name
kind                = "Linux"
reserved            = true
sku {
tier = "Basic"
size = "B1"
}
}

resource "azurerm_app_service" "main" {
name                = "teams-agent-app"
location            = azurerm_resource_group.main.location
resource_group_name = azurerm_resource_group.main.name
app_service_plan_id = azurerm_app_service_plan.main.id
site_config {
linux_fx_version = "PYTHON|3.10"
}
app_settings = {
"ENVIRONMENT" = "Production"
}
}

```

---

## Deployment: Azure App Service & GitHub Actions

- **Continuous Deployment**: Use GitHub Actions to build and deploy on push to `main`.
- **Azure Publish Profile**: Store as a GitHub secret (`AZURE_WEBAPP_PUBLISH_PROFILE`).

**Sample `.github/workflows/azure-appservice.yml`:**
```

name: Deploy Python Teams Agent to Azure App Service

on:
push:
branches: [main]

env:
AZURE_WEBAPP_NAME: teams-agent-app
AZURE_WEBAPP_PACKAGE_PATH: '.'

jobs:
build-and-deploy:
runs-on: ubuntu-latest
steps:
- uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'
    
      - name: Install uv
        run: pip install uv
    
      - name: Install dependencies
        run: uv pip install -r requirements.txt
    
      - name: Archive app for deployment
        run: zip -r app.zip .
    
      - name: Deploy to Azure Web App
        uses: azure/webapps-deploy@v3
        with:
          app-name: ${{ env.AZURE_WEBAPP_NAME }}
          publish-profile: ${{ secrets.AZURE_WEBAPP_PUBLISH_PROFILE }}
          package: app.zip
```

---

## Security Notes

- **Never commit secrets**: Use `.env` for local, Azure App Service settings for production.
- **Delegated permissions**: Users must sign in and consent; agent acts strictly within user’s access.
- **Least privilege**: Only request the permissions your agent needs.

---
