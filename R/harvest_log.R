# Generic disclosure-log harvester.
# Usage (from repo root):
#   Rscript R/harvest_log.R <log_slug> <log_url> [agency] [mode=full|html_only] [max_docs] [max_pages]
# Saves raw HTML of every listing page and one level of detail pages, downloads every linked document,
# and writes data/manifest_<log_slug>.csv (one row per item-link, resumable).
script_dir <- dirname(sub("--file=", "", grep("--file=", commandArgs(FALSE), value = TRUE)[1]))
source(file.path(script_dir, "helpers.R"))
source(file.path(script_dir, "harvest_helpers.R"))

HV_COLS <- c("log_slug", "agency", "log_url", "row_key", "item_id", "link_type", "depth", "listing_url", "detail_url",
             "reference", "title", "date_detected", "decision", "item_text", "detail_text", "fields_json", "link_text",
             "doc_url", "fetched_at", "http_status", "local_path", "sha256", "bytes", "content_type", "note")

DOC_EXT <- "pdf|docx?|dotx?|xlsx?|xlsm|xlsb|csv|zip|txt|rtf|odt|ods|odp|pptx?|xml|json|7z|gz|tar|rar|msg|eml|jpe?g|png|tiff?|gif|mp3|mp4|wav|rdf|ics"
DOC_DIR <- "/(sites/default/files|system/files|__data/assets|getmedia|media|download|downloads|files|documents|assets|attachments|file|cdn|sharepoint)/"
MONTHS <- "(Jan(uary)?|Feb(ruary)?|Mar(ch)?|Apr(il)?|May|Jun(e)?|Jul(y)?|Aug(ust)?|Sep(t(ember)?)?|Oct(ober)?|Nov(ember)?|Dec(ember)?)"
DATE_RX <- paste0("\\b\\d{1,2}(st|nd|rd|th)?\\s+", MONTHS, "\\.?,?\\s+\\d{4}\\b|\\b\\d{1,2}/\\d{1,2}/\\d{2,4}\\b|\\b\\d{4}-\\d{2}-\\d{2}\\b|\\b", MONTHS, "\\s+\\d{4}\\b")
REF_RX <- "\\b(?:FOI|LEX|FA|RQ|REQ|CR|DL|OAIC)[-_/ ]?(?:[A-Z]{1,4}[-_/ ])?\\d{2,}[A-Za-z0-9/_-]*"
DEC_RX <- "(?i)(released? in full|full(y)? (release|access)|partial(ly)? (release|access|granted)|access (granted|refused)|refus(ed|al)|exempt|no documents? (found|held)|withdrawn|transferred|part release|release in part)"

get_ref <- function(x) {
  m <- regmatches(x, regexec("(?i)reference( number| no[.])?:?[[:space:]]+(.{3,60}?)[[:space:]]+(release date|publication date|date|decision|summary|applicant|description)", x, perl = TRUE))[[1]]
  if (length(m) >= 4) return(trimws(m[3]))
  first_match(x, REF_RX)
}
# ---- small utilities -----------------------------------------------------------
now_utc <- function() format(Sys.time(), tz = "UTC", "%Y-%m-%dT%H:%M:%SZ")
first_match <- function(x, rx, perl = TRUE) { m <- regmatches(x, regexpr(rx, x, perl = perl)); if (length(m)) m[1] else "" }
strip_frag <- function(u) sub("#.*$", "", u)
norm_host <- function(h) sub("^www\\.", "", tolower(h))
url_path_noq <- function(u) { p <- sub("^https?://[^/]+", "", u); p <- sub("[?#].*$", "", p); p[!nzchar(p)] <- "/"; p }
PAGE_PARAMS <- "(page|p|pg|pagenum|pagenumber|currentpage|paged|offset|start|b_start:int|cp|pageindex|page_no|pageno)"
strip_page_params <- function(u) {
  q <- sub("^[^?]*\\??", "", strip_frag(u)); base <- sub("\\?.*$", "", strip_frag(u))
  if (!nzchar(q) || q == strip_frag(u)) return(base)
  kv <- strsplit(q, "&")[[1]]; keep <- kv[!grepl(paste0("^", PAGE_PARAMS, "="), kv, ignore.case = TRUE)]
  if (length(keep)) paste0(base, "?", paste(keep, collapse = "&")) else base
}

SORT_PARAMS <- "(sort|sort_by|sort_order|order|orderby|order_by|dir|direction|view|items_per_page|per_page|perpage|limit|display)"
canon_url <- function(u) {
  u <- strip_frag(u); if (!grepl("?", u, fixed = TRUE)) return(u)
  pos <- regexpr("?", u, fixed = TRUE); base <- substr(u, 1, pos - 1); q <- substring(u, pos + 1)
  kv <- strsplit(q, "&", fixed = TRUE)[[1]]; paste0(base, "?", paste(sort(kv[nzchar(kv)]), collapse = "&"))
}
has_sort_param <- function(u) grepl(paste0("[?&]", SORT_PARAMS, "="), u, ignore.case = TRUE)
link_class <- function(abs_url, own_host) {
  if (!grepl("^https?://", abs_url)) return(paste0("other:", sub(":.*$", "", abs_url)))
  p <- url_path_noq(abs_url)
  ext <- tolower(sub(".*\\.([A-Za-z0-9]+)$", "\\1", basename(p)))
  has_ext <- grepl("\\.[A-Za-z0-9]{1,5}$", basename(p))
  if (has_ext && grepl(paste0("^(", DOC_EXT, ")$"), ext)) return("document")
  if (!has_ext && grepl(DOC_DIR, p, ignore.case = TRUE) && grepl("[?&]download|/download|/getmedia/|/__data/assets/|/system/files/|/sites/default/files/", abs_url, ignore.case = TRUE)) return("document")
  if (norm_host(host_of(abs_url)) == norm_host(own_host)) "page" else "external"
}

get_root <- function(doc) {
  for (sel in c("main", "[role=main]", "#main-content", "#content", ".main-content", "article")) {
    n <- html_element(doc, sel); if (!inherits(n, "xml_missing")) return(n)
  }
  html_element(doc, "body")
}
clean_root <- function(root) {
  xp <- paste0(".//nav | .//aside | .//script | .//style | .//noscript | .//*[@role='navigation'] | .//*[@role='banner'] | ",
               ".//*[@role='contentinfo'] | .//header[not(ancestor::article) and not(ancestor::li) and not(ancestor::tr)] | ",
               ".//footer[not(ancestor::article) and not(ancestor::li) and not(ancestor::tr)] | ",
               ".//*[contains(@class,'breadcrumb') or contains(@class,'pagination') or contains(@class,'pager') or contains(@class,'skip-link')]")
  for (n in xml_find_all(root, xp)) tryCatch(xml_remove(n), error = function(e) NULL)
  root
}
node_text <- function(n) squish(html_text2(n))
cls_of <- function(x) { v <- xml_attr(x, "class"); v[is.na(v)] <- ""; sub("[[:space:]].*$", "", trimws(v)) }  # first class token only: cards often add modifier classes

# nearest ancestor that is one of several same-shaped siblings that each hold a link
# Repeated blocks of >= 3 same-shaped siblings with real text (cards, table rows, list entries), found WITHOUT
# needing links, so listings whose items have no documents are still captured. Larger groups win over nested smaller ones.
SKIP_TAGS <- c("p", "span", "option", "br", "td", "th", "a", "dd", "dt", "label", "h1", "h2", "h3", "h4", "h5", "h6", "img", "thead", "tbody", "script")
kept_groups <- function(root) {
  cand <- list()
  for (par in c(list(root), as.list(xml_find_all(root, ".//*[count(*) >= 3]")))) {
    kids <- xml_children(par); if (length(kids) < 3) next
    nm <- xml_name(kids); key <- paste(nm, cls_of(kids))
    for (k in unique(key)) {
      idx <- which(key == k); if (length(idx) < 3 || nm[idx[1]] %in% SKIP_TAGS) next
      mem <- kids[idx]; if (mean(nchar(xml_text(mem))) < 40) next
      paths <- vapply(mem, xml_path, ""); cand[[length(cand) + 1]] <- list(members = mem, paths = paths, size = length(idx), depth = nchar(paths[1]) - nchar(gsub("/", "", paths[1], fixed = TRUE)))
    }
  }
  if (!length(cand)) return(list())
  ord <- order(-vapply(cand, `[[`, 0, "size"), -vapply(cand, `[[`, 0, "depth")); kept <- list(); kp <- character()
  for (i in ord) {
    mp <- cand[[i]]$paths
    clash <- any(vapply(mp, function(x) any(startsWith(x, paste0(kp, "/")) | startsWith(kp, paste0(x, "/")) | kp == x), logical(1)))
    if (!clash) { kept[[length(kept) + 1]] <- cand[[i]]; kp <- c(kp, mp) }
  }
  kept
}
find_member <- function(a, member_paths) {
  n <- a; for (h in 1:25) { n <- tryCatch(xml_parent(n), error = function(e) NULL); if (is.null(n) || inherits(n, "xml_missing")) return(NULL); if (xml_path(n) %in% member_paths) return(n) }
  NULL
}

find_container <- function(a, root_path) {
  # Climb from the link; every ancestor that is one of >= 2 same-shaped siblings is a candidate item.
  # Take the candidate with the biggest sibling group (a card among 20 cards beats the 2 <li> inside it); ties go to the lowest.
  n <- a; hops <- 0; best <- NULL; best_size <- 1
  while (hops < 12) {
    p <- xml_parent(n); if (inherits(p, "xml_missing") || xml_name(p) %in% c("body", "html", "main")) break
    kids <- xml_children(p); nm <- xml_name(n); cl <- cls_of(n)
    same <- kids[which(xml_name(kids) == nm & cls_of(kids) == cl)]
    if (length(same) >= 2 && length(same) > best_size) { best <- n; best_size <- length(same) }
    n <- p; hops <- hops + 1
  }
  if (!is.null(best)) return(list(node = best, repeated = TRUE))
  anc <- xml_find_first(a, "ancestor::*[self::tr or self::li or self::article or self::p or self::section][1]")
  if (inherits(anc, "xml_missing")) list(node = a, repeated = FALSE) else list(node = anc, repeated = FALSE)
}

fields_of <- function(node) {
  if (xml_name(node) != "tr") return("")
  cells <- xml_find_all(node, "./td|./th"); vals <- vapply(cells, node_text, "")
  tbl <- xml_find_first(node, "ancestor::table[1]"); hdr <- character()
  if (!inherits(tbl, "xml_missing")) {
    h <- xml_find_all(tbl, ".//thead//th | (.//tr[th])[1]/th"); hdr <- vapply(h, node_text, "")
  }
  names(vals) <- if (length(hdr) == length(vals)) hdr else paste0("col", seq_along(vals))
  as.character(toJSON(as.list(vals), auto_unbox = TRUE))
}

# Extract item-link records from a parsed page. Returns list of items:
# list(id, text, title, fields, links = data.frame(url, text, class), repeated)
extract_items <- function(doc, page_url, own_host, listing_url) {
  root <- clean_root(get_root(doc)); if (inherits(root, "xml_missing")) return(list(items = list(), main_text = ""))
  main_text <- node_text(root)
  kg <- tryCatch(kept_groups(root), error = function(e) list()); member_paths <- unlist(lapply(kg, `[[`, "paths"))
  anchors <- xml_find_all(root, ".//a[@href]"); groups <- list(); order <- character()
  for (a in anchors) {
    href <- trimws(xml_attr(a, "href")); if (!nzchar(href) || grepl("^#|^javascript:", href, ignore.case = TRUE)) next
    abs <- tryCatch(strip_frag(xml2::url_absolute(href, page_url)), error = function(e) NA_character_); if (is.na(abs) || !nzchar(abs)) next
    cls <- link_class(abs, own_host); txt <- node_text(a)
    if (cls == "page" && (strip_page_params(abs) == strip_page_params(page_url) || strip_page_params(abs) == strip_page_params(listing_url) ||
        grepl("^(\\d+|next|previous|prev|first|last|older|newer|[<>]+|\u203a|\u00bb|\u2039|\u00ab|\u2026)$", txt, ignore.case = TRUE))) next
    mn <- if (length(member_paths)) find_member(a, member_paths) else NULL
    ct <- if (!is.null(mn)) list(node = mn, repeated = TRUE) else find_container(a, "")
    key <- xml_path(ct$node)
    if (is.null(groups[[key]])) { groups[[key]] <- list(node = ct$node, repeated = ct$repeated, links = list()); order <- c(order, key) }
    groups[[key]]$links[[length(groups[[key]]$links) + 1]] <- list(url = abs, text = txt, class = cls)
  }
  items <- lapply(order, function(key) {
    g <- groups[[key]]; txt <- node_text(g$node)
    h <- xml_find_first(g$node, ".//h1|.//h2|.//h3|.//h4|.//h5|.//h6|.//strong|.//b")
    title <- if (!inherits(h, "xml_missing")) node_text(h) else ""
    ln <- do.call(rbind, lapply(g$links, as.data.frame))
    ln <- ln[!duplicated(paste(ln$url, ln$class)), , drop = FALSE]
    if (!nzchar(title)) { nd <- ln[ln$class != "document", ]; title <- if (nrow(nd)) nd$text[1] else substr(txt, 1, 150) }
    list(id = substr(digest(paste(page_url, key), algo = "md5"), 1, 12), text = txt, title = title, fields = fields_of(g$node),
         links = ln, repeated = g$repeated, node = g$node, key = key)
  })
  # sibling rows with no links (e.g. "available on request"): keep them as link-less items
  seen_parent <- list()
  for (it in items) if (it$repeated) {
    p <- xml_parent(it$node); pk <- xml_path(p)
    if (!is.null(seen_parent[[pk]])) next
    seen_parent[[pk]] <- TRUE
    nm <- xml_name(it$node); cl <- cls_of(it$node)
    for (k in xml_children(p)) {
      if (xml_name(k) != nm || cls_of(k) != cl) next
      kp <- xml_path(k); if (kp %in% order) next
      t <- node_text(k); if (!nzchar(t) || length(xml_find_all(k, "./th")) > 0 && length(xml_find_all(k, "./td")) == 0) next
      items[[length(items) + 1]] <- list(id = substr(digest(paste(page_url, kp), algo = "md5"), 1, 12), text = t, title = substr(t, 1, 150),
        fields = fields_of(k), links = data.frame(url = character(), text = character(), class = character()), repeated = TRUE, node = k, key = kp)
      order <- c(order, kp)
    }
  }
  for (g in kg) for (k in g$members) {
    kp <- xml_path(k); if (kp %in% order) next
    t <- node_text(k); if (!nzchar(t)) next
    items[[length(items) + 1]] <- list(id = substr(digest(paste(page_url, kp), algo = "md5"), 1, 12), text = t, title = substr(t, 1, 150),
      fields = fields_of(k), links = data.frame(url = character(), text = character(), class = character()), repeated = TRUE, node = k, key = kp)
    order <- c(order, kp)
  }
  list(items = items, main_text = main_text)
}

# next-page / archive links, taken from the WHOLE document (pagination often sits in nav-ish blocks)
find_pagination <- function(doc, page_url, log_url, own_host) {
  out <- character()
  for (a in html_elements(doc, "a[href]")) {
    href <- trimws(xml_attr(a, "href")); if (!nzchar(href) || grepl("^#|^javascript:|^mailto:|^tel:", href)) next
    abs <- tryCatch(strip_frag(xml2::url_absolute(href, page_url)), error = function(e) NA_character_); if (is.na(abs)) next
    if (!grepl("^https?://", abs) || norm_host(host_of(abs)) != norm_host(own_host)) next
    if (link_class(abs, own_host) == "document") next
    if (has_sort_param(abs) && !has_sort_param(log_url)) next
    txt <- node_text(a); rel <- tolower(xml_attr(a, "rel") %||% ""); aria <- tolower(xml_attr(a, "aria-label") %||% "")
    same_listing <- strip_page_params(abs) == strip_page_params(page_url) || strip_page_params(abs) == strip_page_params(log_url) ||
      url_path_noq(abs) == url_path_noq(log_url) || url_path_noq(abs) == url_path_noq(page_url)
    has_pp <- grepl(paste0("[?&]", PAGE_PARAMS, "="), abs, ignore.case = TRUE) || grepl("/page[/-]\\d+/?$", url_path_noq(abs))
    is_next <- grepl("next", rel) || grepl("next", aria) || grepl("^(next( page)?|older( entries| posts)?|more)\\b|^[\u203a\u00bb>]+$", txt, ignore.case = TRUE)
    is_archive <- grepl("^(19|20)\\d\\d([-/]\\d\\d)?$|archive|previous (years|logs)|earlier|^older$", txt, ignore.case = TRUE) &&
      startsWith(url_path_noq(abs), sub("/$", "", url_path_noq(log_url)))
    if ((same_listing && (has_pp || is_next)) || (is_next && startsWith(url_path_noq(abs), dirname(url_path_noq(log_url)))) || is_archive) out <- c(out, abs)
  }
  unique(out)
}

# ---- manifest ---------------------------------------------------------------------
hv_manifest_path <- function(slug) file.path(FC_DATA, paste0("manifest_", slug, ".csv"))
hv_read_manifest <- function(slug) {
  p <- hv_manifest_path(slug)
  if (!file.exists(p)) return(as.data.frame(setNames(rep(list(character()), length(HV_COLS)), HV_COLS)))
  read.csv(p, colClasses = "character", na.strings = character(), check.names = FALSE, encoding = "UTF-8")
}
hv_append <- function(slug, row) {
  out <- setNames(vector("list", length(HV_COLS)), HV_COLS)
  for (n in HV_COLS) out[[n]] <- if (is.null(row[[n]]) || length(row[[n]]) == 0 || is.na(row[[n]][1])) "" else as.character(row[[n]][1])
  p <- hv_manifest_path(slug); ex <- file.exists(p)
  write.table(as.data.frame(out), p, sep = ",", row.names = FALSE, col.names = !ex, append = ex, qmethod = "double", fileEncoding = "UTF-8")
}

# ---- the harvester ------------------------------------------------------------------
harvest_log <- function(log_slug, log_url, agency = "", mode = "full", max_docs = Inf, max_pages = 400, max_detail = 3000, only_refs = NULL) {
  hv_load_blocked()
  own_host <- host_of(log_url)
  base_dir <- file.path(FC_DATA, "raw_html", log_slug)
  dirs <- if (dir.exists(base_dir)) list.dirs(base_dir, recursive = FALSE) else character()
  open <- dirs[!file.exists(file.path(dirs, "_complete"))]
  run_dir <- if (length(open)) tail(sort(open), 1) else file.path(base_dir, format(Sys.Date()))
  dir.create(run_dir, showWarnings = FALSE, recursive = TRUE)
  rel_dir <- sub(paste0("^", FC_ROOT, "/"), "", run_dir)
  idx_path <- file.path(run_dir, "pages_index.csv")
  idx <- if (file.exists(idx_path)) read.csv(idx_path, colClasses = "character") else data.frame(url = character(), file = character(), status = character(), sha256 = character(), fetched_at = character(), final_url = character())
  mf <- hv_read_manifest(log_slug)
  have_keys <- new.env(); for (k in mf$row_key) assign(k, TRUE, envir = have_keys)
  doc_done <- new.env()
  for (i in which(mf$http_status == "200" & nzchar(mf$local_path) & nzchar(mf$doc_url) & mf$link_type == "document")) if (file.exists(file.path(FC_ROOT, mf$local_path[i]))) assign(mf$doc_url[i], i, envir = doc_done)
  st <- list(pages = 0, details = 0, docs_new = 0, docs_attempted = 0, rows = 0, stopped = "")
  log_msg("[%s] start mode=%s url=%s run_dir=%s (manifest rows=%d)", log_slug, mode, log_url, rel_dir, nrow(mf))

  fetch_page <- function(url, file) {
    j <- which(idx$url == url & idx$status == "200")
    if (length(j) && file.exists(file.path(run_dir, idx$file[j[1]]))) return(list(status = 200L, file = file.path(run_dir, idx$file[j[1]]), cached = TRUE, final_url = idx$final_url[j[1]]))
    dest <- file.path(run_dir, file); r <- hv_get(url, dest, kind = "page")
    row <- data.frame(url = url, file = file, status = as.character(r$status), sha256 = if (!is.null(r$path)) sha_file(dest) else "", fetched_at = now_utc(), final_url = r$final_url %||% url)
    write.table(row, idx_path, sep = ",", row.names = FALSE, col.names = !file.exists(idx_path), append = file.exists(idx_path), qmethod = "double")
    idx <<- rbind(idx, row)
    list(status = r$status, file = if (r$status == 200) dest else NULL, cached = FALSE, final_url = r$final_url %||% url, note = r$note)
  }
  emit <- function(row) {
    key <- digest(paste(row$link_type, row$listing_url, row$detail_url, row$doc_url, row$item_id), algo = "md5")
    if (exists(key, envir = have_keys, inherits = FALSE)) return(invisible(FALSE))
    row$row_key <- key; row$log_slug <- log_slug; row$agency <- agency; row$log_url <- log_url
    hv_append(log_slug, row); assign(key, TRUE, envir = have_keys); st$rows <<- st$rows + 1; invisible(TRUE)
  }
  download_doc <- function(url) {   # returns list(status, local_path, sha256, bytes, content_type, note, fetched_at)
    if (exists(url, envir = doc_done, inherits = FALSE)) {
      i <- get(url, envir = doc_done); return(list(status = mf$http_status[i], local_path = mf$local_path[i], sha256 = mf$sha256[i], bytes = mf$bytes[i], content_type = mf$content_type[i], note = "already downloaded", fetched_at = mf$fetched_at[i], skipped = TRUE))
    }
    fn <- safe_name(substr(URLdecode(basename(url_path_noq(url))), 1, 110)); if (!nzchar(fn)) fn <- "download"
    rel <- file.path("data", "raw", log_slug, paste0(substr(digest(url, algo = "md5"), 1, 8), "_", fn))
    dest <- file.path(FC_ROOT, rel); r <- hv_get(url, dest, kind = "doc")
    if (r$status == 0L) return(list(status = "", note = r$note, skipped = TRUE, nofetch = TRUE))
    out <- list(status = as.character(r$status), content_type = r$type %||% "", note = r$note %||% "", fetched_at = now_utc(), skipped = FALSE)
    if (r$status == 200 && file.exists(dest)) {
      if (!grepl("\\.[A-Za-z0-9]{2,5}$", fn)) { e <- hv_ext_from_type(out$content_type); if (nzchar(e)) { nd <- paste0(dest, ".", e); file.rename(dest, nd); dest <- nd; rel <- paste0(rel, ".", e) } }
      out$local_path <- rel; out$sha256 <- sha_file(dest); out$bytes <- as.character(file.size(dest)); assign(url, nrow(mf) + 1L, envir = doc_done)
      mf[nrow(mf) + 1, ] <<- NA_character_; mf$http_status[nrow(mf)] <<- "200"; mf$local_path[nrow(mf)] <<- rel; mf$doc_url[nrow(mf)] <<- url
      mf$sha256[nrow(mf)] <<- out$sha256; mf$bytes[nrow(mf)] <<- out$bytes; mf$content_type[nrow(mf)] <<- out$content_type; mf$fetched_at[nrow(mf)] <<- out$fetched_at
      assign(url, nrow(mf), envir = doc_done)
    }
    out
  }
  stop_all <- function() st$stopped != ""
  process_items <- function(items, page_url, listing_url, depth, detail_url = "", detail_text = "", parent = NULL, detail_queue = NULL) {
    new_details <- list()
    for (it in items) {
      if (stop_all()) break
      txt <- if (!is.null(parent)) parent$text else it$text
      base <- list(item_id = if (!is.null(parent)) parent$id else it$id, depth = depth, listing_url = listing_url, detail_url = detail_url,
                   title = if (!is.null(parent)) parent$title else it$title, item_text = txt, detail_text = detail_text,
                   fields_json = it$fields, reference = get_ref(paste(it$text, txt)),
                   date_detected = first_match(txt, DATE_RX), decision = first_match(txt, DEC_RX))
      if (nrow(it$links) == 0) { emit(c(base, list(link_type = "none", note = "item text only, no links"))); next }
      dl <- 0
      for (k in seq_len(nrow(it$links))) {
        L <- it$links[k, ]; row <- c(base, list(link_text = L$text, doc_url = L$url))
        if (L$class == "document") {
          if (!is.null(only_refs) && !(row$reference %in% only_refs)) { emit(c(row, list(link_type = "document", note = "not in only_refs filter: not downloaded"))); next }
          if (mode == "html_only") { emit(c(row, list(link_type = "document", note = "html_only mode: not downloaded"))); next }
          if (st$docs_attempted >= max_docs) { st$stopped <<- "max_docs reached"; break }
          key <- digest(paste("document", listing_url, detail_url, L$url, row$item_id), algo = "md5")
          if (exists(key, envir = have_keys, inherits = FALSE)) next
          d <- download_doc(L$url)
          if (isTRUE(d$nofetch)) { emit(c(row, list(link_type = "document", note = d$note))); next }
          if (!isTRUE(d$skipped)) { st$docs_new <<- st$docs_new + 1; st$docs_attempted <<- st$docs_attempted + 1
            if (st$docs_new %% 10 == 0) log_msg("[%s] progress: %d documents downloaded, %d pages, %d detail pages, %d manifest rows", log_slug, st$docs_new, st$pages, st$details, st$rows) }
          emit(c(row, list(link_type = "document"), d[c("status", "local_path", "sha256", "bytes", "content_type", "note", "fetched_at")] |> setNames(c("http_status", "local_path", "sha256", "bytes", "content_type", "note", "fetched_at"))))
          if (any(host_of(L$url) %in% .fc$blocked)) { st$stopped <<- paste("host blocked:", host_of(L$url)); break }
        } else if (L$class == "page") {
          emit(c(row, list(link_type = "detail_page", note = "page link in item (followed only if item has no documents or it is a child page; see detail_fetched rows)")))
          lp <- url_path_noq(log_url); up <- url_path_noq(L$url)
          is_anc <- startsWith(sub("/$", "", lp), sub("/$", "", up)) && nchar(up) > 1 || nchar(up) <= 1
          wants <- !any(it$links$class == "document") || startsWith(up, dirname(lp)) || grepl("read more|view|details?|more info|full", L$text, ignore.case = TRUE)
          if (depth == 0 && it$repeated && dl < 3 && !is_anc && wants && !has_sort_param(L$url)) { new_details[[length(new_details) + 1]] <- list(url = L$url, item = it); dl <- dl + 1 }
        } else {
          emit(c(row, list(link_type = L$class, note = "link logged, not fetched")))
        }
      }
    }
    new_details
  }

  # a log URL that is itself a file (e.g. a spreadsheet of releases): download it as a document
  if (link_class(log_url, own_host) == "document") {
    d <- if (mode == "full") download_doc(log_url) else list(note = "html_only mode: not downloaded")
    emit(c(list(link_type = "document", depth = 0, listing_url = log_url, doc_url = log_url, item_id = digest(log_url, algo = "md5")),
           d[intersect(names(d), c("status", "local_path", "sha256", "bytes", "content_type", "note", "fetched_at"))] |> (\(x) setNames(x, sub("^status$", "http_status", names(x))))()))
    writeLines(now_utc(), file.path(run_dir, "_complete")); log_msg("[%s] COMPLETE: log URL is a document", log_slug)
    return(invisible(list(complete = TRUE)))
  }
  # ---- listing pages (BFS over pagination) ----
  queue <- log_url; seen <- canon_url(log_url); hashes <- character(); detail_q <- list(); n <- 0
  while (length(queue) && n < max_pages && !stop_all()) {
    u <- queue[1]; queue <- queue[-1]; n <- n + 1
    r <- fetch_page(u, sprintf("page-%03d.html", n))
    if (r$status != 200) {
      log_msg("[%s] listing page %s -> status %s %s", log_slug, u, r$status, r$note %||% "")
      emit(list(link_type = "listing_error", depth = 0, listing_url = u, http_status = as.character(r$status), note = r$note %||% "", fetched_at = now_utc(), item_id = digest(u, algo = "md5")))
      if (n == 1) { st$stopped <- paste("first page failed", r$status); break } else if (r$status %in% c(401, 403, 429)) { st$stopped <- paste("blocked", r$status); break } else next
    }
    st$pages <- st$pages + 1
    doc <- tryCatch(read_html(r$file), error = function(e) NULL); if (is.null(doc)) { log_msg("[%s] cannot parse %s", log_slug, u); next }
    h <- digest(r$file, algo = "md5", file = TRUE); if (h %in% hashes) { log_msg("[%s] page %s duplicate of an earlier page, skipping", log_slug, u); next }; hashes <- c(hashes, h)
    nxt <- find_pagination(doc, u, log_url, own_host)
    for (x in nxt) if (!(canon_url(x) %in% seen)) { seen <- c(seen, canon_url(x)); queue <- c(queue, x) }
    ex <- extract_items(doc, u, own_host, log_url)
    emit(list(link_type = "listing_page", depth = 0, listing_url = u, local_path = file.path(rel_dir, basename(r$file)), http_status = "200", fetched_at = now_utc(), item_id = digest(u, algo = "md5"),
              detail_text = substr(ex$main_text, 1, 30000), sha256 = sha_file(r$file), bytes = as.character(file.size(r$file)), note = sprintf("%d items", length(ex$items))))
    nd <- process_items(ex$items, u, u, 0)
    detail_q <- c(detail_q, nd)
  }
  # ---- detail pages, one level ----
  dseen <- character(); dn <- 0
  for (d in detail_q) {
    if (stop_all() || dn >= max_detail) break
    if (strip_frag(d$url) %in% dseen || strip_frag(d$url) %in% seen) next
    dseen <- c(dseen, strip_frag(d$url)); dn <- dn + 1
    r <- fetch_page(d$url, sprintf("detail-%05d.html", dn))
    if (r$status != 200) { emit(list(link_type = "detail_error", depth = 1, listing_url = d$item$id, detail_url = d$url, http_status = as.character(r$status), note = r$note %||% "", fetched_at = now_utc(), item_id = d$item$id)); next }
    st$details <- st$details + 1
    doc <- tryCatch(read_html(r$file), error = function(e) NULL); if (is.null(doc)) next
    ex <- extract_items(doc, d$url, own_host, log_url)
    emit(list(link_type = "detail_fetched", depth = 1, listing_url = "", detail_url = d$url, local_path = file.path(rel_dir, basename(r$file)), http_status = "200", fetched_at = now_utc(), item_id = d$item$id,
              title = d$item$title, item_text = d$item$text, detail_text = substr(ex$main_text, 1, 30000), sha256 = sha_file(r$file), bytes = as.character(file.size(r$file)), note = sprintf("%d items", length(ex$items))))
    process_items(ex$items, d$url, d$url, 1, detail_url = d$url, detail_text = substr(ex$main_text, 1, 30000), parent = d$item)
  }
  complete <- !stop_all() && n < max_pages && length(queue) == 0
  if (complete) writeLines(now_utc(), file.path(run_dir, "_complete"))
  log_msg("[%s] %s: pages=%d detail=%d docs_new=%d rows_new=%d stopped=%s", log_slug, if (complete) "COMPLETE" else "INCOMPLETE", st$pages, st$details, st$docs_new, st$rows, st$stopped)
  invisible(c(st, complete = complete))
}

if (sys.nframe() == 0 && length(grep("--file=.*harvest_log\\.R", commandArgs(FALSE))) > 0) {
  a <- commandArgs(TRUE)
  if (length(a) < 2) stop("usage: Rscript R/harvest_log.R <log_slug> <log_url> [agency] [full|html_only] [max_docs] [max_pages]")
  harvest_log(a[1], a[2], agency = if (length(a) >= 3) a[3] else "", mode = if (length(a) >= 4) a[4] else "full",
              max_docs = if (length(a) >= 5) as.numeric(a[5]) else Inf, max_pages = if (length(a) >= 6) as.numeric(a[6]) else 400,
              only_refs = if (length(a) >= 7) readLines(a[7]) else NULL)
}
