# Cloud Monitoring dashboard for the csoh.org Cloud Run origin.
#
# Surfaces what's worth watching now that Cloud Run is a direct Cloudflare
# origin (no GCLB in front): request rate by response class, request latency
# percentiles, and active instance count.
#
# Find it at: GCP Console → Monitoring → Dashboards → "csoh.org Origin".
#
# What these numbers mean: Cloudflare proxies + caches all production traffic,
# so these metrics count only requests that missed Cloudflare's edge cache and
# actually reached Cloud Run. For total-visitor numbers, use Cloudflare zone
# analytics. These are the right answer for "what is our origin doing" —
# cold-start behavior, origin error rates, request volume past the cache.
resource "google_monitoring_dashboard" "csoh_origin" {
  project = var.project_id

  dashboard_json = jsonencode({
    displayName = "csoh.org Origin"
    mosaicLayout = {
      columns = 12
      tiles = [
        {
          width  = 6
          height = 4
          widget = {
            title = "Cloud Run — request rate by response code class"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"cloud_run_revision\" AND resource.label.service_name=\"csoh-site\" AND metric.type=\"run.googleapis.com/request_count\""
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
            title = "Cloud Run — request latency percentiles (ms)"
            xyChart = {
              dataSets = [
                {
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "resource.type=\"cloud_run_revision\" AND resource.label.service_name=\"csoh-site\" AND metric.type=\"run.googleapis.com/request_latencies\""
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
                      filter = "resource.type=\"cloud_run_revision\" AND resource.label.service_name=\"csoh-site\" AND metric.type=\"run.googleapis.com/request_latencies\""
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
                      filter = "resource.type=\"cloud_run_revision\" AND resource.label.service_name=\"csoh-site\" AND metric.type=\"run.googleapis.com/request_latencies\""
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
      ]
    }
  })

  depends_on = [google_project_service.apis]
}
