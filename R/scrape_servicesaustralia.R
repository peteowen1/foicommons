# Source 2: Services Australia FOI disclosure log. Usage: Rscript R/scrape_servicesaustralia.R [max_docs]
# robots.txt asks for Crawl-delay: 10, so this source runs at one request per 10 seconds.
script_dir <- dirname(sub("--file=", "", grep("--file=", commandArgs(FALSE), value = TRUE)[1]))
source(file.path(script_dir, "helpers.R"))
args <- commandArgs(TRUE); max_docs <- if (length(args)) as.integer(args[1]) else Inf
SRC <- "servicesaustralia"; BASE <- "https://www.servicesaustralia.gov.au"
LOG <- paste0(BASE, "/freedom-information-disclosure-log")

r <- fc_html(LOG)
if (r$status != 200) stop("listing failed: ", r$status, " ", r$note)
rows <- html_elements(r$html, "table tbody tr")
log_msg("SA: %d table rows", length(rows))
items <- list()
for (tr in rows) {
  tds <- html_elements(tr, "td"); if (length(tds) < 2) next
  detail <- tds[[2]]; full <- squish(html_text2(detail))
  ref <- regmatches(full, regexpr("LEX ?[0-9]+", full))
  ref <- if (length(ref)) sub("LEX ?", "LEX ", ref) else ""
  lab <- function(l) {
    m <- regmatches(full, regexpr(paste0(l, ": .*?(?= Exemptions:| Sections of the Act:|$)"), full, perl = TRUE))
    if (length(m)) sub(paste0(l, ": "), "", m) else ""
  }
  lis <- squish(html_text2(html_elements(detail, "li")))
  title <- squish(html_text2(html_elements(detail, "p")[[1]]))
  base <- list(source = SRC, reference = ref, release_date = squish(html_text2(tds[[1]])),
               title = paste(c(title, lis), collapse = " | "), agency = "Services Australia", listing_url = LOG,
               detail_text = full, sections_of_act = lab("Sections of the Act"), exemptions = lab("Exemptions"),
               extra_json = as.character(toJSON(list(n_cells = length(tds), list_items = lis), auto_unbox = TRUE)))
  links <- html_elements(detail, "a"); hrefs <- html_attr(links, "href")
  keep <- !is.na(hrefs) & grepl("\\.(pdf|xlsx?|docx?|csv|zip)(\\?|$)", hrefs, ignore.case = TRUE)
  if (!any(keep)) {
    base$doc_url <- ""
    base$note <- if (grepl("available upon request", full)) "documents available upon request (not online)" else ""
    items <- c(items, list(base)); next
  }
  for (i in which(keep)) items <- c(items, list(modifyList(base, list(doc_url = url_absolute(hrefs[i], BASE),
                                                                      doc_title = squish(html_text2(links[[i]]))))))
}
items <- lapply(items, function(i) {
  if (i$reference == "") i$reference <- paste0("noref-", gsub("[^0-9]", "", i$release_date), "-", substr(digest(i$detail_text), 1, 6))
  i
})
log_msg("SA: %d item-document rows", length(items))

mf <- read_manifest(SRC); done <- 0
for (it in items) {
  if (done >= max_docs) break
  if (archive_document(SRC, it, mf, delay = 10)) {
    done <- done + 1; mf <- read_manifest(SRC)
    if (done %% 10 == 0) { log_msg("progress %d", done); manifest_summary(SRC) }
  }
  if ("www.servicesaustralia.gov.au" %in% .fc$blocked) break
}
manifest_summary(SRC)
