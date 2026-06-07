# Azure Front Door + WAF — Global Load Balancing with Edge Security
# Provides: CDN, DDoS, WAF (OWASP rules), SSL offload, geo-filtering

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.85"
    }
  }
}

# ─── WAF Policy ───────────────────────────────────────────────────────
resource "azurerm_cdn_frontdoor_firewall_policy" "platform" {
  name                              = "${var.prefix}-${var.environment}-waf"
  resource_group_name               = var.resource_group_name
  sku_name                          = "Premium_AzureFrontDoor"
  enabled                           = true
  mode                              = var.environment == "production" ? "Prevention" : "Detection"
  redirect_url                      = "https://error.${var.domain_name}"
  custom_block_response_status_code = 403
  custom_block_response_body        = base64encode("{\"error\": \"Request blocked by WAF\", \"code\": \"WAF_BLOCK\"}")

  # OWASP 3.2 managed rule set
  managed_rule {
    type    = "DefaultRuleSet"
    version = "2.0"
    action  = "Block"
    override {
      rule_group_name = "SQLI"
      rule {
        rule_id = "942100"
        action  = "Block"
        enabled = true
      }
    }
    override {
      rule_group_name = "XSS"
      rule {
        rule_id = "941110"
        action  = "Block"
        enabled = true
      }
    }
  }

  # Microsoft Bot Manager
  managed_rule {
    type    = "Microsoft_BotManagerRuleSet"
    version = "1.0"
    action  = "Block"
  }

  # Rate limiting
  custom_rule {
    name                           = "RateLimitPerIP"
    enabled                        = true
    priority                       = 1
    rate_limit_duration_in_minutes = 1
    rate_limit_threshold           = var.waf_rate_limit_per_minute
    type                           = "RateLimitRule"
    action                         = "Block"
    match_condition {
      match_variable     = "RemoteAddr"
      operator           = "IPMatch"
      negation_condition = true
      match_values       = var.waf_allowed_ips
    }
  }

  # Block malicious user agents
  custom_rule {
    name     = "BlockMaliciousUserAgents"
    enabled  = true
    priority = 10
    type     = "MatchRule"
    action   = "Block"
    match_condition {
      match_variable = "RequestHeader"
      selector       = "User-Agent"
      operator       = "Contains"
      match_values   = ["sqlmap", "nikto", "nessus", "acunetix", "zgrab", "python-requests/2"]
    }
  }

  tags = var.tags
}

# ─── Front Door Profile ───────────────────────────────────────────────
resource "azurerm_cdn_frontdoor_profile" "platform" {
  name                     = "${var.prefix}-${var.environment}-afd"
  resource_group_name      = var.resource_group_name
  sku_name                 = "Premium_AzureFrontDoor"
  response_timeout_seconds = 120
  tags                     = var.tags
}

# ─── Endpoint ─────────────────────────────────────────────────────────
resource "azurerm_cdn_frontdoor_endpoint" "platform" {
  name                     = "${var.prefix}-${var.environment}"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.platform.id
  tags                     = var.tags
}

# ─── Origin Group ─────────────────────────────────────────────────────
resource "azurerm_cdn_frontdoor_origin_group" "aks" {
  name                     = "aks-origin-group"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.platform.id
  session_affinity_enabled = false

  load_balancing {
    sample_size                 = 4
    successful_samples_required = 3
    additional_latency_in_milliseconds = 50
  }

  health_probe {
    interval_in_seconds = 30
    path                = "/health/ready"
    protocol            = "Https"
    request_type        = "GET"
  }
}

# ─── Origin (AKS Ingress) ─────────────────────────────────────────────
resource "azurerm_cdn_frontdoor_origin" "aks_primary" {
  name                          = "aks-primary"
  cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.aks.id
  enabled                       = true
  certificate_name_check_enabled = true

  host_name          = var.aks_ingress_fqdn
  http_port          = 80
  https_port         = 443
  origin_host_header = var.aks_ingress_fqdn
  priority           = 1
  weight             = 1000
}

# ─── Route ────────────────────────────────────────────────────────────
resource "azurerm_cdn_frontdoor_route" "api" {
  name                          = "api-route"
  cdn_frontdoor_endpoint_id     = azurerm_cdn_frontdoor_endpoint.platform.id
  cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.aks.id
  cdn_frontdoor_origin_ids      = [azurerm_cdn_frontdoor_origin.aks_primary.id]
  enabled                       = true

  forwarding_protocol    = "HttpsOnly"
  https_redirect_enabled = true
  patterns_to_match      = ["/*"]
  supported_protocols    = ["Http", "Https"]

  cdn_frontdoor_custom_domain_ids = var.custom_domain_ids

  cache {
    query_string_caching_behavior = "IgnoreQueryString"
    compression_enabled           = true
    content_types_to_compress     = ["text/html", "text/css", "application/javascript", "application/json"]
  }

  cdn_frontdoor_rule_set_ids = [azurerm_cdn_frontdoor_rule_set.security_headers.id]
}

# ─── Security Headers Rule Set ────────────────────────────────────────
resource "azurerm_cdn_frontdoor_rule_set" "security_headers" {
  name                     = "securityheaders"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.platform.id
}

resource "azurerm_cdn_frontdoor_rule" "hsts" {
  depends_on                = [azurerm_cdn_frontdoor_origin.aks_primary]
  name                      = "AddHSTS"
  cdn_frontdoor_rule_set_id = azurerm_cdn_frontdoor_rule_set.security_headers.id
  order                     = 1
  behavior_on_match         = "Continue"

  actions {
    response_header_action {
      header_action = "Append"
      header_name   = "Strict-Transport-Security"
      value         = "max-age=31536000; includeSubDomains; preload"
    }
    response_header_action {
      header_action = "Append"
      header_name   = "X-Content-Type-Options"
      value         = "nosniff"
    }
    response_header_action {
      header_action = "Append"
      header_name   = "X-Frame-Options"
      value         = "DENY"
    }
  }
}

# ─── WAF Security Policy ──────────────────────────────────────────────
resource "azurerm_cdn_frontdoor_security_policy" "waf" {
  name                     = "${var.prefix}-${var.environment}-waf-policy"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.platform.id

  security_policies {
    firewall {
      cdn_frontdoor_firewall_policy_id = azurerm_cdn_frontdoor_firewall_policy.platform.id
      association {
        patterns_to_match = ["/*"]
        domain {
          cdn_frontdoor_domain_id = azurerm_cdn_frontdoor_endpoint.platform.id
        }
      }
    }
  }
}

# ─── Variables ────────────────────────────────────────────────────────
variable "prefix" { type = string }
variable "environment" { type = string }
variable "resource_group_name" { type = string }
variable "domain_name" { type = string }
variable "aks_ingress_fqdn" { type = string }
variable "custom_domain_ids" { type = list(string); default = [] }
variable "waf_rate_limit_per_minute" { type = number; default = 1000 }
variable "waf_allowed_ips" { type = list(string); default = [] }
variable "tags" { type = map(string); default = {} }

# ─── Outputs ──────────────────────────────────────────────────────────
output "frontdoor_endpoint_hostname" {
  value = azurerm_cdn_frontdoor_endpoint.platform.host_name
}

output "frontdoor_profile_id" {
  value = azurerm_cdn_frontdoor_profile.platform.id
}
