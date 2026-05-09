# Cloud Monitoring dashboard for csoh.org production.
#
# Surfaces the metrics worth watching at a glance: LB request rate, latency
# percentiles, HTTP response code breakdown, Cloud Armor blocks, and Cloud
# Run instance count. The LB is the layer in front of the application, so
# its metrics reflect every request that made it past Cloudflare's cache.
#
# Find this dashboard at:
#   GCP Console → Monitoring → Dashboards → "csoh.org Overview"
#
# Note on what these numbers mean: Cloudflare proxies + caches production
# traffic. The metrics here only count traffic that wasn't served from
# Cloudflare's edge cache (i.e., requests that actually hit our origin).
# For total-visitor numbers, look at Cloudflare zone analytics. These
# metrics are the right answer for "what's our origin doing" — capacity,
# error rates, attack-traffic volume.
resource "google_monitoring_dashboard" "csoh_overview" {
  project = var.project_id

  dashboard_json = jsonencode({
    displayName = "csoh.org Overview"
    mosaicLayout = {
      columns = 12
      tiles = [
        {
          width  = 6
          height = 4
          widget = {
            title = "Request rate (per minute)"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"https_lb_rule\" AND metric.type=\"loadbalancing.googleapis.com/https/request_count\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_RATE"
                      crossSeriesReducer = "REDUCE_SUM"
                      groupByFields      = ["metric.label.response_code_class"]
                    }
                  }
                }
                plotType   = "STACKED_AREA"
                targetAxis = "Y1"
              }]
              yAxis = {
                label = "req/s"
                scale = "LINEAR"
              }
              chartOptions = { mode = "COLOR" }
            }
          }
        },
        {
          xPos   = 6
          width  = 6
          height = 4
          widget = {
            title = "Total latency percentiles (ms)"
            xyChart = {
              dataSets = [
                {
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "resource.type=\"https_lb_rule\" AND metric.type=\"loadbalancing.googleapis.com/https/total_latencies\""
                      aggregation = {
                        alignmentPeriod    = "60s"
                        perSeriesAligner   = "ALIGN_DELTA"
                        crossSeriesReducer = "REDUCE_PERCENTILE_50"
                      }
                    }
                  }
                  legendTemplate = "p50"
                  plotType       = "LINE"
                  targetAxis     = "Y1"
                },
                {
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "resource.type=\"https_lb_rule\" AND metric.type=\"loadbalancing.googleapis.com/https/total_latencies\""
                      aggregation = {
                        alignmentPeriod    = "60s"
                        perSeriesAligner   = "ALIGN_DELTA"
                        crossSeriesReducer = "REDUCE_PERCENTILE_95"
                      }
                    }
                  }
                  legendTemplate = "p95"
                  plotType       = "LINE"
                  targetAxis     = "Y1"
                },
                {
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "resource.type=\"https_lb_rule\" AND metric.type=\"loadbalancing.googleapis.com/https/total_latencies\""
                      aggregation = {
                        alignmentPeriod    = "60s"
                        perSeriesAligner   = "ALIGN_DELTA"
                        crossSeriesReducer = "REDUCE_PERCENTILE_99"
                      }
                    }
                  }
                  legendTemplate = "p99"
                  plotType       = "LINE"
                  targetAxis     = "Y1"
                },
              ]
              yAxis = {
                label = "ms"
                scale = "LINEAR"
              }
            }
          }
        },
        {
          yPos   = 4
          width  = 6
          height = 4
          widget = {
            title = "Response code breakdown (rate)"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"https_lb_rule\" AND metric.type=\"loadbalancing.googleapis.com/https/request_count\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_RATE"
                      crossSeriesReducer = "REDUCE_SUM"
                      groupByFields      = ["metric.label.response_code"]
                    }
                  }
                }
                plotType   = "STACKED_BAR"
                targetAxis = "Y1"
              }]
              yAxis = {
                label = "req/s by code"
                scale = "LINEAR"
              }
            }
          }
        },
        {
          xPos   = 6
          yPos   = 4
          width  = 6
          height = 4
          widget = {
            title = "Cloud Armor — blocked requests"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"https_lb_rule\" AND metric.type=\"loadbalancing.googleapis.com/https/request_count\" AND metric.label.response_code_class=\"400\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_RATE"
                      crossSeriesReducer = "REDUCE_SUM"
                    }
                  }
                }
                legendTemplate = "4xx (incl. WAF blocks)"
                plotType       = "LINE"
                targetAxis     = "Y1"
              }]
              yAxis = {
                label = "req/s"
                scale = "LINEAR"
              }
            }
          }
        },
        {
          yPos   = 8
          width  = 6
          height = 4
          widget = {
            title = "Cloud Run — active instance count"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"cloud_run_revision\" AND resource.label.service_name=\"csoh-site\" AND metric.type=\"run.googleapis.com/container/instance_count\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_MEAN"
                      crossSeriesReducer = "REDUCE_SUM"
                      groupByFields      = ["metric.label.state"]
                    }
                  }
                }
                plotType   = "STACKED_AREA"
                targetAxis = "Y1"
              }]
              yAxis = {
                label = "instances"
                scale = "LINEAR"
              }
            }
          }
        },
        {
          xPos   = 6
          yPos   = 8
          width  = 6
          height = 4
          widget = {
            title = "Cloud Run — request latency p95 (ms)"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"cloud_run_revision\" AND resource.label.service_name=\"csoh-site\" AND metric.type=\"run.googleapis.com/request_latencies\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_DELTA"
                      crossSeriesReducer = "REDUCE_PERCENTILE_95"
                    }
                  }
                }
                plotType   = "LINE"
                targetAxis = "Y1"
              }]
              yAxis = {
                label = "ms"
                scale = "LINEAR"
              }
            }
          }
        },
      ]
    }
  })

  depends_on = [google_project_service.apis]
}
