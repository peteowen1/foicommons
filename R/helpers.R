# Shared helpers for foicommons archivers: polite HTTP, robots.txt checks,
# resumable manifests. Source this from the per-source scripts.
suppressPackageStartupMessages({ library(httr2); library(rvest); library(xml2); library(jsonlite); library(digest) })

FC_UA   <- "foicommons-archiver/0.1 (personal research archive)"
FC_ROOT <- "C:/dev/foicommons"
FC_DATA <- file.path(FC_ROOT, "data")

`%||%` <- function(a, b) if (is.null(a) || length(a) == 0 || is.na(a[1])) b else a

.fc <- new.env()
.fc$last <- list()      # host -> time of last request
.fc$robots <- list()    # host -> list(rules, delay)
.fc$blocked <- character()

log_msg <- function(...) cat(format(Sys.time(), "%H:%M:%S"), sprintf(...), "\n", sep = " ")

host_of <- function(url) sub("^https?://([^/:]+).*$", "\\1", url)
path_of <- function(url) { p <- sub("^https?://[^/]+", "", url); if (!nzchar(p)) "/" else p }

# ---- robots.txt ------------------------------------------------------------
rule_to_regex <- function(rule) {
  anchored <- grepl("\\$$", rule); rule <- sub("\\$$", "", rule)
  rx <- gsub("([.+?^(){}|\\[\\]\\\\])", "\\\\\\1", rule, perl = TRUE)
  rx <- gsub("\\*", ".*", rx)
  paste0("^", rx, if (anchored) "$" else "")
}
load_robots <- function(host) {
  if (!is.null(.fc$robots[[host]])) return(.fc$robots[[host]])
  txt <- tryCatch({
    throttle(host, 3)
    resp <- request(paste0("https://", host, "/robots.txt")) |> req_user_agent(FC_UA) |>
      req_error(is_error = \(r) FALSE) |> req_timeout(30) |> req_perform()
    if (resp_status(resp) == 200) resp_body_string(resp) else ""
  }, error = function(e) "")
  lines <- trimws(sub("#.*$", "", strsplit(txt, "\r?\n")[[1]]))
  ua_star <- FALSE; rules <- list(); delay <- NA_real_
  for (l in lines) {
    if (grepl("^user-agent:", l, ignore.case = TRUE)) {
      ua_star <- trimws(sub("^[^:]*:", "", l)) == "*"
    } else if (ua_star && grepl("^(dis)?allow:", l, ignore.case = TRUE)) {
      type <- tolower(sub(":.*$", "", l)); val <- trimws(sub("^[^:]*:", "", l))
      if (nzchar(val)) rules[[length(rules) + 1]] <- list(type = type, rx = rule_to_regex(val), len = nchar(val))
    } else if (ua_star && grepl("^crawl-delay:", l, ignore.case = TRUE)) {
      delay <- as.numeric(trimws(sub("^[^:]*:", "", l)))
    }
  }
  .fc$robots[[host]] <- list(rules = rules, delay = delay)
  .fc$robots[[host]]
}
# Longest matching rule wins; allow wins ties (Google semantics).
robots_ok <- function(url) {
  r <- load_robots(host_of(url)); p <- path_of(url); best <- NULL
  for (ru in r$rules) if (grepl(ru$rx, p)) {
    if (is.null(best) || ru$len > best$len || (ru$len == best$len && ru$type == "allow")) best <- ru
  }
  is.null(best) || best$type == "allow"
}
host_delay <- function(host, default = 3) { d <- load_robots(host)$delay; max(default, if (is.na(d)) 0 else d) }

# ---- throttled fetch ---------------------------------------------------------
throttle <- function(host, delay) {
  last <- .fc$last[[host]]
  if (!is.null(last)) { w <- delay - as.numeric(difftime(Sys.time(), last, units = "secs")); if (w > 0) Sys.sleep(w) }
  .fc$last[[host]] <- Sys.time()
}

# Blocks persist across runs in the same file harvest_helpers.R uses (data/registry/blocked_hosts.csv).
# Before 8 October 2026 fc_get kept them in memory only, so the next run of scrape_dss.R,
# scrape_servicesaustralia.R or wayback.R would try a host that had answered 403/429.
FC_BLOCKED_FILE <- file.path(FC_DATA, "registry", "blocked_hosts.csv")
fc_load_blocked <- function() {
  if (isTRUE(.fc$blocked_loaded)) return(invisible())
  if (file.exists(FC_BLOCKED_FILE)) .fc$blocked <- unique(c(.fc$blocked, read.csv(FC_BLOCKED_FILE, colClasses = "character")$host))
  .fc$blocked_loaded <- TRUE
}
fc_record_block <- function(host, status, url) {
  .fc$blocked <- unique(c(.fc$blocked, host))
  known <- if (file.exists(FC_BLOCKED_FILE)) read.csv(FC_BLOCKED_FILE, colClasses = "character")$host else character()
  if (host %in% known) return(invisible())
  dir.create(dirname(FC_BLOCKED_FILE), showWarnings = FALSE, recursive = TRUE)
  ex <- file.exists(FC_BLOCKED_FILE)
  write.table(data.frame(host = host, blocked_at = format(Sys.time(), tz = "UTC"), status = status, url = url, why = "fc_get"),
              FC_BLOCKED_FILE, sep = ",", row.names = FALSE, col.names = !ex, append = ex, qmethod = "double")
}

# Returns list(status, body, path, type, note). Never bypasses blocks: a 403/429 marks the
# host blocked (in memory and in blocked_hosts.csv) and later calls to it return status 0.
fc_get <- function(url, dest = NULL, delay = NULL) {
  fc_load_blocked()
  host <- host_of(url)
  if (host %in% .fc$blocked) return(list(status = 0L, note = "host blocked earlier (this run or recorded in blocked_hosts.csv)"))
  if (!robots_ok(url)) return(list(status = 0L, note = "disallowed by robots.txt"))
  if (is.null(delay)) delay <- host_delay(host)
  throttle(host, delay)
  req <- request(url) |> req_user_agent(FC_UA) |> req_error(is_error = \(r) FALSE) |>
    req_timeout(900) |> req_retry(max_tries = 2, is_transient = \(r) resp_status(r) >= 500)
  resp <- tryCatch(if (is.null(dest)) req_perform(req) else req_perform(req, path = dest), error = function(e) e)
  .fc$last[[host]] <- Sys.time()   # count from the END of the request (big downloads)
  if (inherits(resp, "error")) return(list(status = -1L, note = conditionMessage(resp)))
  st <- resp_status(resp)
  if (st %in% c(403, 429)) { fc_record_block(host, st, url); log_msg("BLOCKED %s on %s - stopping this host", st, host) }
  list(status = st, body = if (is.null(dest) && st < 400) resp_body_raw(resp) else NULL, path = dest,
       type = resp_header(resp, "content-type") %||% "", note = "")
}
fc_html <- function(url) { r <- fc_get(url); if (r$status == 200) r$html <- read_html(r$body); r }

# ---- manifests ---------------------------------------------------------------
# One row per (item, document). Items with no downloadable document get one row with empty doc_url.
MANIFEST_COLS <- c("source","reference","title","release_date","publication_date","decision","agency","applicant",
                   "doc_title","doc_url","doc_size_label","listing_url","detail_text","sections_of_act","exemptions",
                   "extra_json","fetched_at","http_status","local_path","sha256","bytes","note")
manifest_path <- function(source) file.path(FC_DATA, paste0("manifest_", source, ".csv"))
read_manifest <- function(source) {
  p <- manifest_path(source)
  if (!file.exists(p)) return(as.data.frame(setNames(rep(list(character()), length(MANIFEST_COLS)), MANIFEST_COLS)))
  read.csv(p, colClasses = "character", na.strings = character(), check.names = FALSE, encoding = "UTF-8")
}
append_manifest <- function(source, row) {
  row <- as.list(row); out <- setNames(vector("list", length(MANIFEST_COLS)), MANIFEST_COLS)
  for (n in MANIFEST_COLS) out[[n]] <- if (is.null(row[[n]]) || length(row[[n]]) == 0 || is.na(row[[n]][1])) "" else as.character(row[[n]][1])
  p <- manifest_path(source); dir.create(dirname(p), showWarnings = FALSE, recursive = TRUE)
  ex <- file.exists(p)
  write.table(as.data.frame(out), p, sep = ",", row.names = FALSE, col.names = !ex, append = ex,
              qmethod = "double", fileEncoding = "UTF-8")
}
sha_file <- function(p) digest(p, algo = "sha256", file = TRUE)
safe_name <- function(x) gsub("[^A-Za-z0-9._-]+", "_", x)
squish <- function(x) trimws(gsub("[[:space:]]+", " ", x))

# Download one document for an item (list), resumable. Returns TRUE if work was done, FALSE if skipped.
archive_document <- function(source, item, mf, delay = NULL) {
  now <- format(Sys.time(), tz = "UTC", usetz = FALSE)
  if (!nzchar(item$doc_url %||% "")) {
    if (!any(mf$reference == item$reference & mf$doc_url == "")) {
      item$fetched_at <- now; if (!nzchar(item$note %||% "")) item$note <- "no document link on listing"
      append_manifest(source, item); return(TRUE)
    }
    return(FALSE)
  }
  prev <- mf[mf$doc_url == item$doc_url & mf$reference == item$reference & mf$http_status == "200", , drop = FALSE]
  if (nrow(prev) > 0) {
    lp <- file.path(FC_ROOT, prev$local_path[nrow(prev)])
    if (file.exists(lp) && sha_file(lp) == prev$sha256[nrow(prev)]) return(FALSE)
  }
  rel <- file.path("data", "raw", source, safe_name(item$reference), safe_name(basename(sub("[?#].*$", "", item$doc_url))))
  dest <- file.path(FC_ROOT, rel); dir.create(dirname(dest), showWarnings = FALSE, recursive = TRUE)
  tmp <- paste0(dest, ".part")
  r <- fc_get(item$doc_url, dest = tmp, delay = delay)
  if (r$status == 0L) return(FALSE)   # blocked / robots: do not log as a failure row, caller stops
  item$fetched_at <- now; item$http_status <- r$status; item$note <- r$note
  if (r$status == 200 && file.exists(tmp)) {
    file.rename(tmp, dest); item$local_path <- rel; item$sha256 <- sha_file(dest); item$bytes <- file.size(dest)
  } else if (file.exists(tmp)) file.remove(tmp)
  append_manifest(source, item)
  TRUE
}

manifest_summary <- function(source) {
  m <- read_manifest(source); ok <- m[m$http_status == "200", ]
  cat(sprintf("[%s] rows=%d items=%d docs_ok=%d size=%.1f MB failures=%d\n", source, nrow(m), length(unique(m$reference)),
              nrow(ok), sum(as.numeric(ok$bytes)) / 1e6, sum(!(m$http_status %in% c("200", "")))))
}
