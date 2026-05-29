output "load_balancer_hostname" {
  description = "The active/active LB hostname (the production site)."
  value       = cloudflare_load_balancer.site.name
}

output "pool_id" {
  description = "Load Balancer pool holding the three cloud origins."
  value       = cloudflare_load_balancer_pool.origins.id
}

output "monitor_id" {
  description = "Health monitor ID."
  value       = cloudflare_load_balancer_monitor.site.id
}
