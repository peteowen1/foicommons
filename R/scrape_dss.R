# Source 1: DSS FOI disclosure log. Usage: Rscript R/scrape_dss.R [max_docs]
script_dir <- dirname(sub("--file=", "", grep("--file=", commandArgs(FALSE), value = TRUE)[1]))
source(file.path(script_dir, "helpers.R"))
args <- commandArgs(TRUE); max_docs <- if (length(args)) as.integer(args[1]) else Inf
SRC <- "dss"; BASE <- "https://www.dss.gov.au"
LOG <- paste0(BASE, "/access-information/freedom-information/our-freedom-information-disclosure-log")

parse_card <- function(card, page_url) {
  txt <- function(sel) { e <- html_element(card, sel); if (inherits(e, "xml_missing")) "" else squish(html_text2(e)) }
  # every label/value pair on the card, kept verbatim so unknown fields survive
  pairs <- list()
  for (d in html_elements(card, ".ct-foi-card__content > div")) {
    lab <- html_element(d, ".ct-foi-card__label"); if (inherits(lab, "xml_missing")) next
    if (grepl("ct-foi-card__documents", html_attr(d, "class"))) next
    v <- html_element(d, ".ct-foi-card__value, .ct-foi-card__request-content")
    pairs[[squish(html_text2(lab))]] <- if (inherits(v, "xml_missing")) "" else squish(html_text2(v))
  }
  pub <- html_attr(html_element(card, ".ct-foi-card__date time:not(.ct-timestamp__start)"), "datetime")
  base <- list(source = SRC, reference = pairs[["Reference number"]] %||% "", release_date = pairs[["Release date"]] %||% "",
               publication_date = pub %||% "", decision = pairs[["Decision"]] %||% "",
               title = pairs[["Summary of request"]] %||% "", detail_text = pairs[["Summary of request"]] %||% "",
               listing_url = page_url, agency = "Department of Social Services",
               extra_json = as.character(toJSON(pairs, auto_unbox = TRUE)))
  links <- html_elements(card, ".ct-foi-card__documents-list a")
  if (length(links) == 0) return(list(modifyList(base, list(doc_url = ""))))
  lapply(links, function(a) modifyList(base, list(doc_url = url_absolute(html_attr(a, "href"), BASE),
                                                 doc_title = html_attr(a, "title") %||% "",
                                                 doc_size_label = squish(html_text2(a)))))
}

items <- list(); page <- 0
repeat {
  r <- fc_html(sprintf("%s?page=%d", LOG, page))
  if (r$status != 200) { log_msg("listing page %d status %s %s - stopping listing", page, r$status, r$note); break }
  cards <- html_elements(r$html, ".ct-foi-card")
  log_msg("listing page %d: %d cards", page, length(cards))
  if (length(cards) == 0) break
  for (cd in cards) items <- c(items, parse_card(cd, sprintf("%s?page=%d", LOG, page)))
  page <- page + 1
}
keys <- vapply(items, \(i) paste(i$reference, i$doc_url), "")
items <- items[!duplicated(keys)]
log_msg("DSS: %d item-document rows from %d listing pages", length(items), page)

mf <- read_manifest(SRC); done <- 0
for (it in items) {
  if (done >= max_docs) break
  if (archive_document(SRC, it, mf)) {
    done <- done + 1; mf <- read_manifest(SRC)
    if (done %% 10 == 0) { log_msg("progress %d", done); manifest_summary(SRC) }
  }
  if ("www.dss.gov.au" %in% .fc$blocked) break
}
manifest_summary(SRC)
