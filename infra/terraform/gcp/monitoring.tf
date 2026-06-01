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
# analytics. These are the right answer for "what is our origin doing" -
# cold-start behavior, origin error rates, request volume past the cache.
# A "resource" block tells Terraform to CREATE and manage a real cloud object.
# The two strings are (1) the resource TYPE - here a Cloud Monitoring
# dashboard - and (2) a local NAME ("csoh_origin") used only inside this
# Terraform code to refer back to this object. (Contrast with a "data" source,
# which only READS something that already exists instead of creating it.)
resource "google_monitoring_dashboard" "csoh_origin" {
  # Which GCP project this dashboard lives in. `var.project_id` reads the
  # `project_id` variable defined in variables.tf (default "csoh-org-495800").
  # `var.<name>` is how Terraform references a variable's value.
  project = var.project_id

  # Cloud Monitoring dashboards are configured by a single JSON document. The
  # `jsonencode(...)` function takes the readable Terraform object below (curly
  # braces, lists, key = value) and turns it into the JSON string the GCP API
  # expects. Writing it as a Terraform object instead of raw JSON lets us use
  # comments and keeps quoting sane.
  dashboard_json = jsonencode({
    # The human-readable name shown in the Monitoring → Dashboards list.
    displayName = "csoh.org Origin"
    # A "mosaic" layout places widgets on a grid. The grid is `columns` wide
    # (12 here, a common 12-column design grid), and each tile below states its
    # own size and position in those grid units.
    mosaicLayout = {
      columns = 12
      # `tiles` is the list of chart panels on the dashboard. Each element is
      # one widget plus where/how big it sits on the 12-column grid.
      tiles = [
        # Tile 1: top-left panel, 6 columns wide (half the grid) and 4 rows
        # tall. With no xPos/yPos it defaults to the top-left (0,0) corner.
        {
          width  = 6
          height = 4
          # `widget` is the actual chart drawn inside this tile.
          widget = {
            title = "Cloud Run - request rate by response code class"
            # `xyChart` = a time-series line/area chart (X = time, Y = value).
            xyChart = {
              # `dataSets` = the one or more series of data plotted on this
              # chart. This chart has a single data set.
              dataSets = [{
                # `timeSeriesQuery` describes WHICH metric data to fetch and
                # HOW to aggregate it before plotting.
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    # The `filter` selects which raw metric time series to pull.
                    # In English: requests to the Cloud Run service named
                    # "csoh-site", using GCP's built-in request_count metric.
                    # `resource.type="cloud_run_revision"` scopes it to Cloud
                    # Run; the inner quotes are escaped (\") because the whole
                    # filter is itself a double-quoted string.
                    filter = "resource.type=\"cloud_run_revision\" AND resource.label.service_name=\"csoh-site\" AND metric.type=\"run.googleapis.com/request_count\""
                    # `aggregation` collapses the raw data points into something
                    # plottable. Monitoring does this in two steps:
                    aggregation = {
                      # 1) Per-series ALIGNMENT: bucket each series into fixed
                      #    60-second windows. ALIGN_RATE converts the running
                      #    request COUNT into a per-second RATE (requests/sec).
                      alignmentPeriod  = "60s"
                      perSeriesAligner = "ALIGN_RATE"
                      # 2) CROSS-series REDUCTION: combine the now-aligned
                      #    series. REDUCE_SUM adds them up so all Cloud Run
                      #    revisions are summed into one total.
                      crossSeriesReducer = "REDUCE_SUM"
                      # ...but keep them split out by HTTP status class (2xx,
                      # 4xx, 5xx) so we can see the mix of successes vs errors.
                      groupByFields = ["metric.label.response_code_class"]
                    }
                  }
                }
                # STACKED_AREA stacks the per-class series on top of each other,
                # so total height = total req/s and each band is one status
                # class - a quick read on how much traffic is erroring.
                plotType = "STACKED_AREA"
                # Plot against the primary (left) Y axis, named "Y1".
                targetAxis = "Y1"
              }]
              # Label and scale for that left Y axis. LINEAR = evenly spaced
              # (as opposed to logarithmic).
              yAxis = {
                label = "req/s"
                scale = "LINEAR"
              }
              # Render filled areas in color (vs. grayscale).
              chartOptions = { mode = "COLOR" }
            }
          }
        },
        # Tile 2: top-right panel. `xPos = 6` shifts it 6 columns to the right
        # so it sits beside Tile 1 (which occupies columns 0-5). Same 6x4 size.
        {
          xPos   = 6
          width  = 6
          height = 4
          widget = {
            title = "Cloud Run - request latency percentiles (ms)"
            xyChart = {
              # Three data sets on one chart: the 50th, 95th, and 99th
              # percentile of request latency. A percentile answers "X% of
              # requests were at least this fast." p50 is the typical request;
              # p99 is the slow tail (often where cold starts show up).
              dataSets = [
                # Data set 1: p50 (median latency).
                {
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      # Same Cloud Run service, but the request_latencies metric
                      # (time taken to serve each request) instead of a count.
                      filter = "resource.type=\"cloud_run_revision\" AND resource.label.service_name=\"csoh-site\" AND metric.type=\"run.googleapis.com/request_latencies\""
                      aggregation = {
                        alignmentPeriod = "60s"
                        # ALIGN_DELTA gathers the new latency samples in each
                        # 60s window (latency is a distribution, not a rate).
                        perSeriesAligner = "ALIGN_DELTA"
                        # Reduce across series by taking the 50th percentile.
                        crossSeriesReducer = "REDUCE_PERCENTILE_50"
                      }
                    }
                  }
                  # `legendTemplate` is the label shown in the chart legend.
                  legendTemplate = "p50"
                  # A plain line (not stacked) - these series overlay, not add.
                  plotType   = "LINE"
                  targetAxis = "Y1"
                },
                # Data set 2: p95. Identical to p50 above except the reducer is
                # REDUCE_PERCENTILE_95 (95% of requests were at least this fast).
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
                # Data set 3: p99, the slow tail. Same as above with
                # REDUCE_PERCENTILE_99 - the slowest 1% of requests.
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
              # Y axis measured in milliseconds.
              yAxis = {
                label = "ms"
                scale = "LINEAR"
              }
            }
          }
        },
        # Tile 3: second row, left. `yPos = 4` drops it below Tile 1 (which is
        # 4 rows tall and starts at the top), giving an L-shaped layout.
        {
          yPos   = 4
          width  = 6
          height = 4
          widget = {
            title = "Cloud Run - active instance count"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    # instance_count = how many container instances Cloud Run is
                    # running. This service scales to zero, so watching this
                    # shows cold-start scale-ups when traffic misses the cache.
                    filter = "resource.type=\"cloud_run_revision\" AND resource.label.service_name=\"csoh-site\" AND metric.type=\"run.googleapis.com/container/instance_count\""
                    aggregation = {
                      alignmentPeriod = "60s"
                      # ALIGN_MEAN = average instance count within each window.
                      perSeriesAligner   = "ALIGN_MEAN"
                      crossSeriesReducer = "REDUCE_SUM"
                      # Split by instance `state` (e.g. active vs idle) so the
                      # stacked bands show how many instances are doing work.
                      groupByFields = ["metric.label.state"]
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

  # `depends_on` forces an ordering: Terraform must finish creating the
  # `google_project_service.apis` resources (which enable the Monitoring API,
  # among others, in apis.tf) BEFORE it tries to create this dashboard.
  # Without this, a fresh project might reject the call because the Monitoring
  # API isn't on yet. This is an explicit dependency; Terraform usually infers
  # ordering automatically when one resource references another's attribute.
  depends_on = [google_project_service.apis]
}
