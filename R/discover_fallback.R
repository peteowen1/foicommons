# Second discovery pass for agencies where build_registry.R found no FOI page or no disclosure log.
# Tries /sitemap.xml (and children of a sitemap index) for URLs that look like a disclosure log or FOI page,
# then a longer list of guessed paths (information publication scheme pages etc.).
# Updates data/registry/discovery.csv in place (how_found says which method). Re-run build_registry.R afterwards
# to reassemble agencies.csv (it skips agencies already in discovery.csv).
script_dir <- dirname(sub("--file=", "", grep("--file=", commandArgs(FALSE), value = TRUE)[1]))
source(file.path(script_dir, "helpers.R")); source(file.path(script_dir, "harvest_helpers.R")); source(file.path(script_dir, "harvest_log.R"))
REG_DIR <- file.path(FC_DATA, "registry"); DISC <- file.path(REG_DIR, "discovery.csv"); HTML_DIR <- file.path(REG_DIR, "discovery_html")
FOI_RX <- "freedom[ _-]*of[ _-]*information|freedom[ _-]*information|(^|[/ _-])foi([/ _.-]|$)"
LOG_RX <- "disclosure[ _-]*log|foi[ _-]*log|foi[ _-]*disclosure|released[ _-]*(under|documents|foi)"
GUESS <- c("/about/freedom-of-information", "/about/freedom-information", "/about-us/freedom-information", "/about/foi", "/foi",
           "/information-publication-scheme", "/about-us/information-publication-scheme", "/about/information-publication-scheme",
           "/about-us/access-to-information", "/access-to-information", "/access-information/freedom-information",
           "/about/legislation-and-policy/freedom-information", "/freedom-of-information-foi", "/about-us/freedom-of-information-foi",
           "/about/corporate-information/freedom-of-information", "/about-us/corporate-information/freedom-of-information")
sitemap_urls <- function(base, slug) {
  out <- character(); todo <- paste0(base, c("/sitemap.xml")); n <- 0
  while (length(todo) && n < 6) {
    u <- todo[1]; todo <- todo[-1]; n <- n + 1
    dest <- file.path(HTML_DIR, slug, sprintf("sitemap-%d.xml", n)); r <- hv_get(u, dest, kind = "page")
    if (r$status != 200 || file.size(dest) > 30e6) next
    x <- tryCatch(read_xml(dest), error = function(e) NULL); if (is.null(x)) next
    locs <- xml_text(xml_find_all(x, "//*[local-name()='loc']"))
    if (grepl("sitemapindex", xml_name(xml_root(x)))) todo <- c(todo, head(locs, 5)) else out <- c(out, locs)
  }
  unique(out)
}
page_links <- function(file, base) {
  doc <- read_html(file); a <- html_elements(doc, "a[href]"); if (!length(a)) return(data.frame(url = character(), text = character()))
  h <- html_attr(a, "href"); t <- vapply(a, node_text, "")
  u <- vapply(h, function(x) tryCatch(strip_frag(xml2::url_absolute(trimws(x), base)), error = function(e) NA_character_), "")
  d <- data.frame(url = u, text = t); d[!is.na(d$url) & grepl("^https?://", d$url) & !duplicated(d$url), ]
}
fallback <- function(r) {
  site <- trimws(r$website); if (!grepl("^https?://", site)) site <- paste0("https://", site); base <- sub("^(https?://[^/]+).*$", "\\1", site)
  su <- sitemap_urls(base, r$slug)
  logs <- su[grepl(LOG_RX, su, ignore.case = TRUE)]
  if (length(logs)) { r$log_urls <- paste(head(logs, 8), collapse = " | "); r$status <- "found_log"; r$how_found <- "sitemap.xml url match"
    if (!nzchar(r$foi_page_url)) r$foi_page_url <- (su[grepl(FOI_RX, su, ignore.case = TRUE)])[1] %||% ""; return(r) }
  cand <- c(head(su[grepl(FOI_RX, su, ignore.case = TRUE)][order(nchar(su[grepl(FOI_RX, su, ignore.case = TRUE)]))], 3), paste0(base, GUESS))
  if (nzchar(r$foi_page_url)) cand <- c(r$foi_page_url, cand)
  for (u in unique(cand)) {
    dest <- file.path(HTML_DIR, r$slug, "fb.html"); g <- hv_get(u, dest, kind = "page")
    if (g$status %in% c(401, 403, 429) || (g$status == 0 && grepl("blocked", g$note %||% ""))) { r$status <- "blocked"; r$notes <- paste(r$notes, "fallback: blocked"); return(r) }
    if (g$status != 200 || strip_page_params(g$final_url) == strip_page_params(base)) next
    lk <- page_links(dest, g$final_url); hit <- lk[grepl(LOG_RX, paste(lk$url, lk$text), ignore.case = TRUE) & !grepl("^mailto", lk$url), ]
    if (nrow(hit)) { r$log_urls <- paste(head(unique(hit$url), 8), collapse = " | "); r$foi_page_url <- g$final_url; r$status <- "found_log"; r$how_found <- "fallback: guessed/sitemap page -> disclosure log link"; return(r) }
    txt <- node_text(read_html(dest)); nd <- sum(vapply(lk$url, function(x) link_class(x, host_of(u)) == "document", logical(1)))
    if (grepl("disclosure log", txt, ignore.case = TRUE) && nd >= 3) { r$log_urls <- g$final_url; r$foi_page_url <- g$final_url; r$status <- "found_log"; r$how_found <- "fallback: page is the log"; return(r) }
    if (!nzchar(r$foi_page_url) && grepl(FOI_RX, paste(g$final_url, txt), ignore.case = TRUE)) { r$foi_page_url <- g$final_url; r$status <- "foi_page_only"; r$how_found <- "fallback: guessed path" }
  }
  r$notes <- paste(r$notes, "fallback pass done"); r
}
hv_load_blocked()
d <- read.csv(DISC, colClasses = "character", na.strings = character(), encoding = "UTF-8")
for (i in which(d$status %in% c("no_foi_found", "foi_page_only") & !grepl("fallback pass done", d$notes) & nzchar(d$website))) {
  if (host_of(sub("^(?!https?://)", "https://", d$website[i], perl = TRUE)) %in% .fc$blocked) next
  d[i, ] <- tryCatch(fallback(as.list(d[i, ])), error = function(e) { x <- d[i, ]; x$notes <- paste(x$notes, "fallback error:", conditionMessage(e)); x })
  write.csv(d, DISC, row.names = FALSE, fileEncoding = "UTF-8")
  log_msg("fallback %s -> %s %s", d$slug[i], d$status[i], d$log_urls[i])
}
cat("fallback pass complete\n"); print(table(d$status))
