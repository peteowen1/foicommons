# Walk data/registry/agencies.csv and harvest every disclosure log, one at a time. Resumable:
# a log marked "done" in data/registry/harvest_status.csv is skipped; an interrupted log resumes
# from its open run folder (pages re-used from disk, finished documents skipped).
#   Rscript R/run_all.R              # all logs, registry order
#   Rscript R/run_all.R refresh      # re-harvest logs already marked done (new dated snapshot)
#   Rscript R/run_all.R only=<log_slug>[,<log_slug>]
script_dir <- dirname(sub("--file=", "", grep("--file=", commandArgs(FALSE), value = TRUE)[1]))
source(file.path(script_dir, "helpers.R"))
source(file.path(script_dir, "harvest_helpers.R"))
source(file.path(script_dir, "harvest_log.R"))
args <- commandArgs(TRUE); refresh <- "refresh" %in% args
only <- sub("^only=", "", grep("^only=", args, value = TRUE)); only <- if (length(only)) strsplit(only, ",")[[1]] else character()
HTML_ONLY <- c("dss-main", "servicesaustralia-log")   # documents for these were archived by the phase 1 scrapers

reg <- read.csv(file.path(FC_DATA, "registry", "agencies.csv"), colClasses = "character", encoding = "UTF-8")
reg <- reg[nzchar(reg$disclosure_log_url) & reg$status != "blocked", ]
reg <- reg[order(as.numeric(reg$run_order)), ]
if (length(only)) reg <- reg[reg$log_slug %in% only, ]
STATUS <- file.path(FC_DATA, "registry", "harvest_status.csv")
read_status <- function() if (file.exists(STATUS)) read.csv(STATUS, colClasses = "character") else data.frame(log_slug = character(), status = character())
hv_load_blocked()
total_docs <- 0
log_msg("RUN START: %d logs in registry order (refresh=%s)", nrow(reg), refresh)
for (i in seq_len(nrow(reg))) {
  r <- reg[i, ]; stt <- read_status()
  if (!refresh && any(stt$log_slug == r$log_slug & stt$status == "done")) { next }
  if (host_of(r$disclosure_log_url) %in% .fc$blocked) { log_msg("[%s] skipped: host blocked", r$log_slug); next }
  res <- tryCatch(harvest_log(r$log_slug, r$disclosure_log_url, agency = r$agency, mode = if (r$log_slug %in% HTML_ONLY) "html_only" else "full"),
                  error = function(e) { log_msg("[%s] ERROR %s", r$log_slug, conditionMessage(e)); list(complete = FALSE, stopped = conditionMessage(e)) })
  status <- if (isTRUE(res$complete)) "done" else if (grepl("blocked|403|429", res$stopped %||% "")) "blocked" else "incomplete"
  total_docs <- total_docs + (res$docs_new %||% 0)
  row <- data.frame(log_slug = r$log_slug, status = status, finished_at = format(Sys.time(), tz = "UTC"), pages = res$pages %||% 0, details = res$details %||% 0, docs_new = res$docs_new %||% 0, note = res$stopped %||% "")
  write.table(row, STATUS, sep = ",", row.names = FALSE, col.names = !file.exists(STATUS), append = file.exists(STATUS), qmethod = "double")
  log_msg("SUMMARY %d/%d logs processed; %d new documents this run", i, nrow(reg), total_docs)
}
log_msg("DONE")
