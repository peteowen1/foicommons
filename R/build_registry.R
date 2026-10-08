# Build data/registry/agencies.csv: Commonwealth entities (from the Australian Government
# Organisations Register, AGOR) and their FOI disclosure log URL(s).
#   Rscript R/build_registry.R            # discover (resumable) then assemble
# Source CSV: data/registry/source/agor-2026-06-30.csv (data.gov.au, dataset
# australian-government-organisations-register; same data as directory.gov.au).
# Discovery: homepage -> link whose text/href mentions freedom of information -> that page ->
# links mentioning disclosure log. Results appended to data/registry/discovery.csv after each agency.
script_dir <- dirname(sub("--file=", "", grep("--file=", commandArgs(FALSE), value = TRUE)[1]))
source(file.path(script_dir, "helpers.R"))
source(file.path(script_dir, "harvest_helpers.R"))
source(file.path(script_dir, "harvest_log.R"))   # link_class(), node_text() etc. (CLI block does not fire when sourced)

REG_DIR <- file.path(FC_DATA, "registry"); AGOR <- file.path(REG_DIR, "source", "agor-2026-06-30.csv")
DISC <- file.path(REG_DIR, "discovery.csv"); HTML_DIR <- file.path(REG_DIR, "discovery_html")
slugify <- function(x) { s <- gsub("[^a-z0-9]+", "-", tolower(x)); s <- gsub("^-|-$", "", s); substr(s, 1, 60) }

agor <- read.csv(AGOR, check.names = FALSE, colClasses = "character", encoding = "UTF-8")
agor <- agor[grepl("^[ABC]\\.", agor$`Type of Body`) & agor$Classification == "A. Primary body", ]   # entities that are bodies in their own right
agor$slug <- make.unique(slugify(agor$Title), sep = "-")
agor$asl <- suppressWarnings(as.numeric(gsub(",", "", agor$`Average Staffing Level (ASL)`)))
agor <- agor[order(-ifelse(is.na(agor$asl), -1, agor$asl), agor$Title), ]
agor$run_order <- seq_len(nrow(agor))
cat("AGOR primary bodies in scope:", nrow(agor), "\n")

FOI_RX <- "freedom[ _-]*of[ _-]*information|freedom[ _-]*information|(^|[/ _-])foi([/ _.-]|$)"
LOG_RX <- "disclosure[ _-]*log|foi[ _-]*log|foi[ _-]*disclosure|information[ _-]*released|released[ _-]*(under|documents|foi)|freedom of information (requests|disclosures|documents)"

page_links <- function(file, base) {
  doc <- read_html(file); a <- html_elements(doc, "a[href]")
  if (!length(a)) return(data.frame(url = character(), text = character()))
  h <- html_attr(a, "href"); t <- vapply(a, node_text, "")
  u <- vapply(h, function(x) tryCatch(strip_frag(xml2::url_absolute(trimws(x), base)), error = function(e) NA_character_), "")
  d <- data.frame(url = u, text = t, stringsAsFactors = FALSE); d <- d[!is.na(d$url) & grepl("^https?://", d$url) & !duplicated(d$url), ]; d
}
fetch_to <- function(url, slug, name) { dest <- file.path(HTML_DIR, slug, name); r <- hv_get(url, dest, kind = "page"); r$dest <- dest; r }

discover <- function(row) {
  slug <- row$slug; site <- trimws(row$`Website Address`)
  res <- list(slug = slug, website = site, foi_page_url = "", log_urls = "", how_found = "", status = "", notes = "")
  if (!nzchar(site)) { res$status <- "no_website"; return(res) }
  if (!grepl("^https?://", site)) site <- paste0("https://", site)
  h <- fetch_to(site, slug, "home.html")
  if (h$status != 200) { res$status <- if (h$status == 0) (if (grepl("blocked", h$note)) "blocked" else "robots_disallowed") else if (h$status %in% c(401, 403, 429)) "blocked" else "unreachable"
    res$notes <- paste0("homepage status ", h$status, " ", h$note); return(res) }
  base <- h$final_url; lk <- page_links(h$dest, base)
  foi <- lk[grepl(FOI_RX, paste(lk$url, lk$text), ignore.case = TRUE) & !grepl("^mailto", lk$url), ]
  foi <- foi[order(nchar(url_path_noq(foi$url))), ]
  how <- "homepage link"
  if (!nrow(foi)) {
    how <- "guessed path"; foi <- data.frame(url = character(), text = character())
    for (p in c("/freedom-of-information", "/foi", "/about-us/freedom-of-information", "/about/freedom-of-information", "/about-us/freedom-information")) {
      g <- fetch_to(paste0(sub("^(https?://[^/]+).*$", "\\1", base), p), slug, "guess.html")
      if (g$status == 200 && strip_page_params(g$final_url) != strip_page_params(base)) { foi <- data.frame(url = g$final_url, text = "guess"); break }
      if (g$status == 0 || g$status %in% c(401, 403, 429)) break
    }
  }
  if (!nrow(foi)) { res$status <- "no_foi_found"; res$notes <- "no FOI link on homepage; 5 guessed paths 404"; return(res) }
  foi <- head(foi, 3); logs <- character(); chosen <- ""; n <- 0
  for (u in foi$url) {
    n <- n + 1; r <- fetch_to(u, slug, sprintf("foi-%d.html", n)); if (r$status != 200) next
    if (!nzchar(chosen)) chosen <- u
    lk2 <- page_links(r$dest, r$final_url)
    hit <- lk2[grepl(LOG_RX, paste(lk2$url, lk2$text), ignore.case = TRUE) & !grepl("^mailto", lk2$url), ]
    hit <- hit[!grepl("\\.(pdf|docx?)$", url_path_noq(hit$url), ignore.case = TRUE) | grepl("log", hit$text, ignore.case = TRUE), ]
    if (nrow(hit)) { logs <- unique(hit$url); chosen <- u; break }
    doc <- read_html(r$dest); txt <- node_text(doc)
    ndoc <- sum(vapply(lk2$url, function(x) link_class(x, host_of(u)) == "document", logical(1)))
    if (grepl("disclosure log", txt, ignore.case = TRUE) && ndoc >= 3) { logs <- r$final_url; how <- "foi page is the log"; chosen <- u; break }
  }
  res$foi_page_url <- chosen
  if (length(logs)) { res$log_urls <- paste(head(logs, 8), collapse = " | "); res$status <- "found_log"; if (how == "guessed path") how <- "guessed path then FOI page link" else if (how == "homepage link") how <- "homepage -> FOI page -> disclosure log link" }
  else if (nzchar(chosen)) { res$status <- "foi_page_only"; res$notes <- "FOI page found, no disclosure log link detected" }
  else { res$status <- "foi_page_unreachable" }
  res$how_found <- how; res
}

hv_load_blocked()
done <- if (file.exists(DISC)) read.csv(DISC, colClasses = "character")$slug else character()
seeds <- list("department-of-social-services" = list(
  foi_page_url = "https://www.dss.gov.au/access-information/freedom-information",
  log_urls = paste("https://www.dss.gov.au/access-information/freedom-information/our-freedom-information-disclosure-log",
                   "https://www.dss.gov.au/access-information/freedom-information/portfolio-agencies-freedom-information-disclosure-log",
                   "https://www.dss.gov.au/access-information/freedom-information/portfolio-ministers-freedom-information-disclosure-log", sep = " | ")),
  "services-australia" = list(foi_page_url = "https://www.servicesaustralia.gov.au/freedom-of-information",
                              log_urls = "https://www.servicesaustralia.gov.au/freedom-information-disclosure-log"))
for (i in seq_len(nrow(agor))) {
  row <- agor[i, ]; if (row$slug %in% done) next
  if (row$slug %in% names(seeds)) {
    s <- seeds[[row$slug]]; res <- list(slug = row$slug, website = row$`Website Address`, foi_page_url = s$foi_page_url, log_urls = s$log_urls,
         how_found = "seed from phase 1 (known URLs)", status = "found_log", notes = "")
  } else res <- tryCatch(discover(row), error = function(e) list(slug = row$slug, website = row$`Website Address`, foi_page_url = "", log_urls = "", how_found = "", status = "error", notes = conditionMessage(e)))
  d <- as.data.frame(res, stringsAsFactors = FALSE)
  write.table(d, DISC, sep = ",", row.names = FALSE, col.names = !file.exists(DISC), append = file.exists(DISC), qmethod = "double", fileEncoding = "UTF-8")
  log_msg("[%d/%d] %s -> %s %s", i, nrow(agor), row$Title, res$status, res$log_urls)
}

# ---- assemble agencies.csv: one row per log (agencies without a log keep one row) ----
# An agency's FOI page can link to OTHER agencies' disclosure logs (ANAO's links to PMC, Treasury and
# Infrastructure; ARENA's to DCCEEW). Keeping those harvested the same documents twice under the wrong
# agency (19% duplicate downloads, 8 October 2026). Drop a log on another host unless it is a known
# legitimate case. Slugs are still computed over the full list, so surviving logs keep their old slug and
# their manifest (renaming one would re-harvest it from scratch).
LOG_HOST_OK <- c("cer.gov.au", "nzea.gov.au", "publichospitalfunding.gov.au", "webarchive.nla.gov.au")
bare_host <- function(u) sub("^www\\.", "", tolower(host_of(if (grepl("^https?://", u)) u else paste0("http://", u))))
foreign_log <- function(u, site) {
  h <- bare_host(u); s <- bare_host(site)
  !(h == s || endsWith(h, paste0(".", s)) || endsWith(s, paste0(".", h)) || h %in% LOG_HOST_OK)
}
dropped <- character()
disc <- read.csv(DISC, colClasses = "character", encoding = "UTF-8", na.strings = character())
rows <- list(); used <- character()
for (i in seq_len(nrow(agor))) {
  a <- agor[i, ]; d <- disc[disc$slug == a$slug, ][1, ]
  logs <- if (nzchar(d$log_urls)) trimws(strsplit(d$log_urls, "\\|")[[1]]) else ""
  n_kept <- 0
  for (j in c(seq_along(logs), 0L)) {   # j = 0: placeholder row for an agency whose every log was dropped
    if (j == 0L && n_kept > 0) break
    u <- if (j == 0L) "" else logs[j]; lslug <- if (nzchar(u) && length(logs) > 1) paste0(substr(a$slug, 1, 40), "-", substr(slugify(sub("/$", "", basename(url_path_noq(u)))), 1, 30)) else a$slug
    lslug <- gsub("-+$", "", lslug); if (lslug %in% used) lslug <- paste0(lslug, "-", j); used <- c(used, lslug)
    if (nzchar(u) && a$slug == "department-of-social-services" && grepl("our-freedom", u)) lslug <- "dss-main"
    if (nzchar(u) && a$slug == "services-australia") lslug <- "servicesaustralia-log"
    if (nzchar(u) && a$slug == "department-of-social-services" && grepl("portfolio-agencies", u)) lslug <- "dss-portfolio-agencies"
    if (nzchar(u) && a$slug == "department-of-social-services" && grepl("portfolio-ministers", u)) lslug <- "dss-portfolio-ministers"
    if (j > 0L && nzchar(u) && foreign_log(u, a$`Website Address`)) { dropped <- c(dropped, sprintf("%s -> %s", a$Title, u)); next }
    if (j == 0L) lslug <- a$slug
    n_kept <- n_kept + 1
    ok <- if (nzchar(u)) tryCatch(as.character(robots_ok(u)), error = function(e) "") else ""
    blocked <- if (nzchar(u) && host_of(u) %in% .fc$blocked) "blocked" else if (j == 0L) "foreign_logs_only" else d$status
    rows[[length(rows) + 1]] <- data.frame(run_order = a$run_order, agency = a$Title, agency_slug = a$slug, log_slug = lslug, portfolio = a$Portfolio,
      website = a$`Website Address`, foi_page_url = d$foi_page_url, disclosure_log_url = u, how_found = d$how_found, robots_ok = ok,
      status = blocked, notes = d$notes, agor_id = a$Id, agor_type_of_body = a$`Type of Body`, agor_asl = a$`Average Staffing Level (ASL)`, stringsAsFactors = FALSE)
  }
}
out <- do.call(rbind, rows)
# keep every other AGOR field verbatim as agor_* columns
extra <- agor[match(out$agor_id, agor$Id), setdiff(names(agor), c("Title", "Portfolio", "Website Address", "Id", "Type of Body", "slug", "asl", "run_order", "Average Staffing Level (ASL)"))]
names(extra) <- paste0("agor_", gsub("[^a-z0-9]+", "_", tolower(names(extra))))
res_df <- cbind(out, extra)
res_df[] <- lapply(res_df, function(x) gsub("[\r\n]+", " ", enc2utf8(iconv(as.character(x), "UTF-8", "UTF-8", sub = ""))))
write.csv(res_df, file.path(REG_DIR, "agencies.csv"), row.names = FALSE, fileEncoding = "UTF-8")
cat(sprintf("dropped %d log URLs on another agency's host:\n", length(dropped))); cat(paste0("  ", dropped, "\n"), sep = "")
cat(sprintf("agencies.csv: %d rows, %d agencies, %d with a log URL; statuses:\n", nrow(out), length(unique(out$agency_slug)), sum(nzchar(out$disclosure_log_url))))
print(table(out$status))
