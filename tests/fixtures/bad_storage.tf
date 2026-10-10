resource "azurerm_storage_account" "bad" {
  name                     = "badstorage"
  resource_group_name      = "rg-test"
  location                 = "westeurope"
  account_tier             = "Standard"
  account_replication_type = "LRS"

  # Missing: enable_https_traffic_only
  # Missing: blob_properties encryption
  # Missing: network_rules (public access allowed by default)
  # Missing: required tags (environment, owner, cost_center)
}
