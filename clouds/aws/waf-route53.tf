# AWS WAF v2 + Route53 — Edge Security and DNS
# Provides: OWASP managed rules, rate limiting, geo-blocking, health routing

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.30"
    }
  }
}

# ─── WAF Web ACL ──────────────────────────────────────────────────────
resource "aws_wafv2_web_acl" "platform" {
  provider    = aws.us-east-1  # WAF for CloudFront must be in us-east-1
  name        = "${var.prefix}-${var.environment}-waf"
  description = "Platform WAF — OWASP rules, rate limiting, bot protection"
  scope       = "CLOUDFRONT"

  default_action {
    allow {}
  }

  # AWS Managed — Core Rule Set (OWASP Top 10)
  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 1
    override_action { none {} }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
        rule_action_override {
          action_to_use { count {} }
          name = "SizeRestrictions_BODY"
        }
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "AWSManagedRulesCommonRuleSetMetric"
      sampled_requests_enabled   = true
    }
  }

  # AWS Managed — SQL Injection
  rule {
    name     = "AWSManagedRulesSQLiRuleSet"
    priority = 2
    override_action { none {} }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesSQLiRuleSet"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "SQLiRuleSetMetric"
      sampled_requests_enabled   = true
    }
  }

  # AWS Managed — Known Bad Inputs
  rule {
    name     = "AWSManagedRulesKnownBadInputsRuleSet"
    priority = 3
    override_action { none {} }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "KnownBadInputsMetric"
      sampled_requests_enabled   = true
    }
  }

  # AWS Managed — Bot Control
  rule {
    name     = "AWSManagedRulesBotControlRuleSet"
    priority = 4
    override_action { none {} }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesBotControlRuleSet"
        vendor_name = "AWS"
        managed_rule_group_configs {
          aws_managed_rules_bot_control_rule_set {
            inspection_level = "COMMON"
          }
        }
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "BotControlMetric"
      sampled_requests_enabled   = true
    }
  }

  # Rate Limiting — 1000 req/min per IP
  rule {
    name     = "RateLimitPerIP"
    priority = 10
    action { block {} }
    statement {
      rate_based_statement {
        limit              = var.waf_rate_limit
        aggregate_key_type = "IP"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "RateLimitMetric"
      sampled_requests_enabled   = true
    }
  }

  # Geo blocking (optional)
  dynamic "rule" {
    for_each = length(var.blocked_countries) > 0 ? [1] : []
    content {
      name     = "GeoBlock"
      priority = 5
      action { block {} }
      statement {
        geo_match_statement {
          country_codes = var.blocked_countries
        }
      }
      visibility_config {
        cloudwatch_metrics_enabled = true
        metric_name                = "GeoBlockMetric"
        sampled_requests_enabled   = true
      }
    }
  }

  tags = var.tags

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${var.prefix}-${var.environment}-waf"
    sampled_requests_enabled   = true
  }
}

# ─── Route53 Hosted Zone ──────────────────────────────────────────────
data "aws_route53_zone" "primary" {
  name         = var.domain_name
  private_zone = false
}

# ─── CloudFront Distribution ──────────────────────────────────────────
resource "aws_cloudfront_distribution" "platform" {
  provider = aws.us-east-1
  enabled  = true
  comment  = "${var.prefix}-${var.environment} platform CDN"
  aliases  = ["*.${var.domain_name}", var.domain_name]

  web_acl_id = aws_wafv2_web_acl.platform.arn

  origin {
    domain_name = var.eks_alb_dns_name
    origin_id   = "eks-alb"
    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
    custom_header {
      name  = "X-Custom-Header"
      value = var.cloudfront_origin_secret
    }
  }

  default_cache_behavior {
    allowed_methods        = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "eks-alb"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true
    min_ttl                = 0
    default_ttl            = 0
    max_ttl                = 0

    forwarded_values {
      query_string = true
      headers      = ["Authorization", "Content-Type", "Accept", "Origin"]
      cookies { forward = "none" }
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = length(var.blocked_countries) > 0 ? "blacklist" : "none"
      locations        = var.blocked_countries
    }
  }

  viewer_certificate {
    acm_certificate_arn      = var.acm_certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  tags = var.tags
}

# ─── Route53 Records ──────────────────────────────────────────────────
resource "aws_route53_record" "apex" {
  zone_id = data.aws_route53_zone.primary.zone_id
  name    = var.domain_name
  type    = "A"
  alias {
    name                   = aws_cloudfront_distribution.platform.domain_name
    zone_id                = aws_cloudfront_distribution.platform.hosted_zone_id
    evaluate_target_health = false
  }
}

resource "aws_route53_record" "wildcard" {
  zone_id = data.aws_route53_zone.primary.zone_id
  name    = "*.${var.domain_name}"
  type    = "A"
  alias {
    name                   = aws_cloudfront_distribution.platform.domain_name
    zone_id                = aws_cloudfront_distribution.platform.hosted_zone_id
    evaluate_target_health = false
  }
}

# ─── Route53 Health Check ─────────────────────────────────────────────
resource "aws_route53_health_check" "primary" {
  fqdn              = var.domain_name
  port              = 443
  type              = "HTTPS"
  resource_path     = "/health/ready"
  failure_threshold = 3
  request_interval  = 30
  tags = merge(var.tags, { Name = "${var.prefix}-${var.environment}-health-check" })
}

# ─── Variables ────────────────────────────────────────────────────────
variable "prefix" { type = string }
variable "environment" { type = string }
variable "domain_name" { type = string }
variable "eks_alb_dns_name" { type = string }
variable "acm_certificate_arn" { type = string }
variable "cloudfront_origin_secret" { type = string; sensitive = true }
variable "waf_rate_limit" { type = number; default = 1000 }
variable "blocked_countries" { type = list(string); default = [] }
variable "tags" { type = map(string); default = {} }

# ─── Outputs ──────────────────────────────────────────────────────────
output "cloudfront_domain_name" { value = aws_cloudfront_distribution.platform.domain_name }
output "waf_acl_arn" { value = aws_wafv2_web_acl.platform.arn }
output "route53_zone_id" { value = data.aws_route53_zone.primary.zone_id }
