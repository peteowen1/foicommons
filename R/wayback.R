# Internet Archive (Wayback Machine) history for a disclosure log: agencies drop documents after about two
# years, and DSS moved its whole site in late 2024, so most of its FOI history now exists only in the archive.
#   Rscript R/wayback.R pages   # every distinct archived version of the old log pages -> data/raw_html/wayback/dss/
#   Rscript R/wayback.R parse   # entries and file links from those pages -> data/wayback/dss_entries.csv
#   Rscript R/wayback.R files   # archived copies of the linked files -> data/raw/dss_wayback/, manifest_dss_wayback.csv
# Resumable: each stage skips what is already on disk. Politeness: the project's User-Agent, one request per 3 s
# to web.archive.org through fc_get (which stops the host on 403/429). Raw captures come from `id_` URLs, which
# return the file as archived, without the Wayback toolbar.
script_dir <- dirname(sub("--file=", "", grep("--file=", commandArgs(FALSE), value = TRUE)[1]))
source(file.path(script_dir, "helpers.R"))
args <- commandArgs(TRUE); stage <- if (length(args)) args[1] else "pages"

CDX <- "https://web.archive.org/cdx/search/cdx"
OLD_LOG <- "dss.gov.au/about-the-department/freedom-of-information/disclosure-log"
PAGES_DIR <- file.path(FC_DATA, "raw_html", "wayback", "dss")
OUT_DIR <- file.path(FC_DATA, "wayback")
dir.create(PAGES_DIR, showWarnings = FALSE, recursive = TRUE); dir.create(OUT_DIR, showWarnings = FALSE, recursive = TRUE)

cdx <- function(params) {
  url <- paste0(CDX, "?", paste(names(params), vapply(params, URLencode, "", reserved = TRUE), sep = "=", collapse = "&"))
  r <- fc_get(url)
  if (r$status != 200) stop(sprintf("CDX query failed (%s %s): %s", r$status, r$note, url))
  m <- fromJSON(rawToChar(r$body))
  if (length(m) == 0) return(data.frame())
  setNames(as.data.frame(m[-1, , drop = FALSE], stringsAsFactors = FALSE), m[1, ])
}
raw_url <- function(ts, original) sprintf("https://web.archive.org/web/%sid_/%s", ts, original)

stage_pages <- function() {
  q <- function(url) cdx(list(url = url, matchType = "prefix", output = "json", fl = "original,timestamp,digest,statuscode,mimetype",
                              filter = "statuscode:200", filter = "mimetype:text/html", collapse = "digest"))
  # The log itself, plus the per-year logs for 2010-11 and 2011-12, which sat at the site root
  idx <- rbind(q(OLD_LOG), q("dss.gov.au/disclosure-log-20"))
  idx <- idx[!duplicated(idx$digest), ]
  write.csv(idx, file.path(OUT_DIR, "dss_log_versions.csv"), row.names = FALSE)
  log_msg("[wayback dss] %d distinct versions of the old log pages", nrow(idx))
  for (i in seq_len(nrow(idx))) {
    dest <- file.path(PAGES_DIR, sprintf("%s_%s.html", idx$timestamp[i], substr(safe_name(sub(".*disclosure-log", "", idx$original[i])), 1, 60)))
    if (file.exists(dest)) next
    r <- fc_get(raw_url(idx$timestamp[i], idx$original[i]), dest = paste0(dest, ".part"))
    if (r$status == 0L) stop("stopped: ", r$note)
    if (r$status == 200) file.rename(paste0(dest, ".part"), dest) else {
      unlink(paste0(dest, ".part")); log_msg("[wayback dss] %s for %s %s", r$status, idx$timestamp[i], idx$original[i])
    }
  }
  log_msg("[wayback dss] pages on disk: %d of %d", length(list.files(PAGES_DIR, "\\.html$")), nrow(idx))
}

# Two layouts. 2019 on: Drupal view, 4 columns (reference, date with <time datetime>, request, documents).
# 2014-2018: 5 columns (reference, dd/mm/yyyy, request, published information with links, description), where
# extra documents sit on continuation rows with a blank reference. Every file link is kept with its row text.
FILE_RX <- "(/sites/default/files/|\\.(pdf|docx?|rtf|xlsx?|zip)([?#].*)?$)"
stage_parse <- function() {
  files <- sort(list.files(PAGES_DIR, "\\.html$", full.names = TRUE))
  out <- list(); n_rows <- 0
  for (f in files) {
    ts <- sub("_.*", "", basename(f))
    page <- read_html(f)
    for (tr in html_elements(page, "table tr")) {
      tds <- html_elements(tr, "td")
      if (length(tds) < 3) next
      n_rows <- n_rows + 1
      txt <- squish(html_text2(tds))
      dt <- html_attr(html_element(tds[2], "time"), "datetime")
      if (nzchar(txt[1])) {
        cur <- list(reference = txt[1], date = if (!is.na(dt)) dt else txt[2], request = txt[3],
                    description = if (length(txt) >= 5) txt[5] else "")
      } else if (!exists("cur", inherits = FALSE)) next
      for (a in html_elements(tr, "a")) {
        href <- html_attr(a, "href") %||% ""
        if (!grepl(FILE_RX, href, ignore.case = TRUE)) next
        out[[length(out) + 1]] <- data.frame(snapshot = ts, page = basename(f), reference = cur$reference, date = cur$date,
          request = cur$request, description = if (nzchar(txt[1])) cur$description else txt[length(txt)],
          doc_url = url_absolute(href, "https://www.dss.gov.au/"), link_text = squish(html_text2(a)))
      }
    }
    rm(list = intersect("cur", ls()))
  }
  links <- do.call(rbind, out)
  links$doc_url <- sub("^http://", "https://", sub("//dss\\.gov\\.au", "//www.dss.gov.au", links$doc_url))
  # One row per (reference, file): first and last archived page that listed it
  key <- paste(links$reference, links$doc_url)
  first <- links[!duplicated(key), ]
  first$first_seen <- first$snapshot
  first$last_seen <- tapply(links$snapshot, key, max)[paste(first$reference, first$doc_url)]
  first$snapshot <- NULL; first$page <- NULL
  write.csv(first, file.path(OUT_DIR, "dss_entries.csv"), row.names = FALSE, fileEncoding = "UTF-8")
  log_msg("[wayback dss] %d pages, %d table rows, %d file links, %d distinct (reference, file), %d references, %d files",
          length(files), n_rows, nrow(links), nrow(first), length(unique(first$reference)), length(unique(first$doc_url)))
}

# Files: one request each. The `id_` address at the date the log listed the file redirects to the nearest
# archived capture, so no index lookup is needed; hv_get follows the redirects politely and returns the final
# address, whose timestamp is the capture actually used. Files whose name we already hold from the live log are
# skipped. A capture that is not the file (an archived error page) is kept out and recorded.
stage_files <- function() {
  source(file.path(script_dir, "harvest_helpers.R")); hv_load_blocked()
  e <- read.csv(file.path(OUT_DIR, "dss_entries.csv"), colClasses = "character", encoding = "UTF-8")
  held <- tolower(basename(list.files(file.path(FC_DATA, "raw", "dss"), recursive = TRUE)))
  e <- e[!duplicated(e$doc_url), ]
  todo <- e[!tolower(basename(sub("[?#].*$", "", e$doc_url))) %in% held, ]
  SRC <- "dss_wayback"; mf <- read_manifest(SRC)
  done <- mf$doc_url[mf$http_status %in% c("200", "404", "not-the-file")]
  todo <- todo[!todo$doc_url %in% done, ]
  if (length(args) > 1) todo <- head(todo, as.integer(args[2]))   # trial runs: Rscript R/wayback.R files 3
  log_msg("[wayback dss] %d distinct files listed; %d already held from the live log; %d to fetch now",
          nrow(e), sum(tolower(basename(sub("[?#].*$", "", e$doc_url))) %in% held), nrow(todo))
  magic <- list(pdf = "%PDF", docx = "PK", xlsx = "PK", zip = "PK", rtf = "{\\rtf", doc = rawToChar(as.raw(c(0xD0, 0xCF))))
  for (i in seq_len(nrow(todo))) {
    x <- todo[i, ]
    rel <- file.path("data", "raw", SRC, safe_name(x$reference), safe_name(basename(sub("[?#].*$", "", x$doc_url))))
    dest <- file.path(FC_ROOT, rel)
    r <- hv_get(raw_url(sub("^(\\d{14}).*", "\\1", x$first_seen), x$doc_url), dest, kind = "doc")
    if (r$status == 0L) { log_msg("[wayback dss] stopped: %s", r$note); break }
    item <- list(source = SRC, reference = x$reference, title = x$request, release_date = x$date, doc_url = x$doc_url,
                 doc_title = x$link_text, detail_text = x$description, agency = "Department of Social Services",
                 listing_url = "https://www.dss.gov.au/about-the-department/freedom-of-information/disclosure-log",
                 extra_json = as.character(toJSON(list(wayback_url = r$final_url, log_first_seen = x$first_seen,
                                                       log_last_seen = x$last_seen), auto_unbox = TRUE)),
                 fetched_at = format(Sys.time(), tz = "UTC"), http_status = r$status, note = r$note %||% "")
    if (r$status == 200) {
      ext <- tolower(tools::file_ext(dest)); head <- readBin(dest, "raw", 8)
      want <- magic[[ext]]
      if (!is.null(want) && !startsWith(rawToChar(head[head != as.raw(0)]), want)) {
        file.remove(dest); item$http_status <- "not-the-file"; item$note <- paste("capture is not a", ext, "file")
      } else { item$local_path <- rel; item$sha256 <- sha_file(dest); item$bytes <- file.size(dest) }
    }
    append_manifest(SRC, item)
    if (i %% 25 == 0) log_msg("[wayback dss] %d of %d files", i, nrow(todo))
  }
  manifest_summary(SRC)
}

if (stage == "pages") stage_pages() else if (stage == "parse") stage_parse() else if (stage == "files") stage_files() else stop("unknown stage: ", stage)
