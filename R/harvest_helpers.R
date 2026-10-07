# Helpers for the generic harvester (phase 1b). Builds on helpers.R (robots, throttle) WITHOUT
# changing it: helpers.R fc_get() holds HTML in memory and follows redirects silently, so this file
# adds hv_get(): streams every response straight to disk, follows redirects one hop at a time
# (each hop gets its own robots check and per-host throttle), and records blocked hosts on disk.
script_dir0 <- dirname(sub("--file=", "", grep("--file=", commandArgs(FALSE), value = TRUE)[1]))
if (!exists("FC_UA")) source(file.path(script_dir0, "helpers.R"))

HV_BLOCKED_FILE <- file.path(FC_DATA, "registry", "blocked_hosts.csv")
.hv <- new.env(); .hv$doc403 <- list(); .hv$fail <- list()

hv_load_blocked <- function() {
  if (file.exists(HV_BLOCKED_FILE)) {
    b <- read.csv(HV_BLOCKED_FILE, colClasses = "character")
    .fc$blocked <- unique(c(.fc$blocked, b$host))
  }
}
hv_mark_blocked <- function(host, status, url, why) {
  if (host %in% .fc$blocked) return(invisible())
  .fc$blocked <- c(.fc$blocked, host)
  dir.create(dirname(HV_BLOCKED_FILE), showWarnings = FALSE, recursive = TRUE)
  ex <- file.exists(HV_BLOCKED_FILE)
  write.table(data.frame(host = host, blocked_at = format(Sys.time(), tz = "UTC"), status = status, url = url, why = why),
              HV_BLOCKED_FILE, sep = ",", row.names = FALSE, col.names = !ex, append = ex, qmethod = "double")
  log_msg("BLOCKED host %s (%s): %s", host, status, why)
}
hv_looks_like_challenge <- function(p) {
  if (!file.exists(p) || file.size(p) > 300000) return(FALSE)
  t <- tryCatch(paste(readLines(p, n = 200, warn = FALSE, encoding = "UTF-8"), collapse = " "), error = function(e) "")
  grepl("Just a moment|cf-chl|cf_chl|Attention Required|captcha|Checking your browser|Access Denied|Request unsuccessful", t, ignore.case = TRUE)
}

# kind = "page" or "doc". Returns list(status, path, type, final_url, note).
# status 0 = not fetched (blocked host or robots), -1 = network error.
hv_get <- function(url, dest, kind = "page", delay = NULL, max_hops = 6) {
  dir.create(dirname(dest), showWarnings = FALSE, recursive = TRUE)
  tmp <- paste0(dest, ".part"); cur <- url; tries5xx <- 0; tries_err <- 0
  for (hop in seq_len(max_hops + 4)) {
    host <- host_of(cur)
    if (host %in% .fc$blocked) return(list(status = 0L, note = paste("host blocked:", host), final_url = cur))
    if (!robots_ok(cur)) return(list(status = 0L, note = "disallowed by robots.txt", final_url = cur))
    d <- if (is.null(delay)) host_delay(host) else max(delay, host_delay(host))
    throttle(host, d)
    req <- request(cur) |> req_user_agent(FC_UA) |> req_options(followlocation = FALSE, connecttimeout = 20) |>
      req_error(is_error = \(r) FALSE) |> req_timeout(if (kind == "doc") 1800 else 60)
    resp <- tryCatch(req_perform(req, path = tmp), error = function(e) e)
    .fc$last[[host]] <- Sys.time()
    if (inherits(resp, "error")) {
      tries_err <- tries_err + 1
      if (tries_err <= 1) { Sys.sleep(10); next }
      .hv$fail[[host]] <- (.hv$fail[[host]] %||% 0) + 1
      if (file.exists(tmp)) file.remove(tmp)
      return(list(status = -1L, note = conditionMessage(resp), final_url = cur))
    }
    .hv$fail[[host]] <- 0
    st <- resp_status(resp)
    if (st %in% c(301, 302, 303, 307, 308)) {
      loc <- resp_header(resp, "location")
      if (is.null(loc) || hop > max_hops) { if (file.exists(tmp)) file.remove(tmp); return(list(status = st, note = "redirect without target/too many", final_url = cur)) }
      cur <- xml2::url_absolute(loc, cur); next
    }
    type <- resp_header(resp, "content-type") %||% ""
    if (st == 429) { hv_mark_blocked(host, st, cur, "429 rate limited"); if (file.exists(tmp)) file.remove(tmp)
      return(list(status = st, note = "429: host marked blocked", final_url = cur)) }
    if (st %in% c(401, 403, 503) && hv_looks_like_challenge(tmp)) {
      hv_mark_blocked(host, st, cur, "challenge / access denied page"); file.remove(tmp)
      return(list(status = st, note = "challenge page: host marked blocked", final_url = cur))
    }
    if (st %in% c(401, 403)) {
      if (kind == "page") { hv_mark_blocked(host, st, cur, "403/401 on a page"); if (file.exists(tmp)) file.remove(tmp)
        return(list(status = st, note = "host marked blocked", final_url = cur)) }
      .hv$doc403[[host]] <- (.hv$doc403[[host]] %||% 0) + 1
      if (.hv$doc403[[host]] >= 3) hv_mark_blocked(host, st, cur, "3 consecutive 403 on documents")
      if (file.exists(tmp)) file.remove(tmp)
      return(list(status = st, note = "forbidden", final_url = cur))
    }
    if (st >= 500 && tries5xx < 2) { tries5xx <- tries5xx + 1; Sys.sleep(10); next }
    if (st == 200) .hv$doc403[[host]] <- 0
    if (st == 200 && file.exists(tmp)) { if (file.exists(dest)) file.remove(dest); file.rename(tmp, dest) }
    else if (file.exists(tmp)) file.remove(tmp)
    return(list(status = st, path = if (st == 200) dest else NULL, type = type, final_url = cur, note = ""))
  }
  list(status = -1L, note = "gave up", final_url = cur)
}

hv_ext_from_type <- function(type) {
  type <- tolower(sub(";.*$", "", type))
  m <- c("application/pdf" = "pdf", "application/msword" = "doc",
         "application/vnd.openxmlformats-officedocument.wordprocessingml.document" = "docx",
         "application/vnd.ms-excel" = "xls",
         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" = "xlsx",
         "text/csv" = "csv", "application/zip" = "zip", "text/plain" = "txt", "application/rtf" = "rtf", "text/html" = "html")
  if (type %in% names(m)) m[[type]] else ""
}
