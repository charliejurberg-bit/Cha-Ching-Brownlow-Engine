# build_history.R — builds data_history/brownlow_votes_1990_2006.csv
# Recon-only vote history. Raw AFLTables club strings, no canonicalisation.
# Reads nothing from the repo. Writes exactly one file, to data_history/.

suppressMessages(library(fitzRoy))

KEEP <- c("Season", "Round", "Date", "Venue", "ID", "Player",
          "Playing.for", "Home.team", "Away.team", "Brownlow.Votes")
FINALS <- c("QF", "EF", "SF", "PF", "GF")

parts <- list()
for (yr in 1990:2006) {
  d <- suppressMessages(as.data.frame(fetch_player_stats_afltables(season = yr)))
  n_all <- nrow(d)

  # H&A only: drop the five finals labels explicitly, belt-and-braces with a
  # numeric-coercion check so any unexpected string label is also dropped.
  d <- d[!(d$Round %in% FINALS), ]
  d <- d[!is.na(suppressWarnings(as.numeric(d$Round))), ]

  d <- d[, KEEP]
  parts[[as.character(yr)]] <- d
  cat(sprintf("%d: %d rows -> %d H&A rows\n", yr, n_all, nrow(d)))
}

out <- do.call(rbind, parts)
rownames(out) <- NULL

cat("\n--- pre-write checks ---\n")
cat("rows:", nrow(out), " cols:", ncol(out), "\n")
cat("column order:", paste(names(out), collapse = ", "), "\n")
for (c1 in KEEP) {
  v <- out[[c1]]
  n <- is.na(v)
  if (is.character(v)) n <- n | trimws(v) == ""
  cat(sprintf("  %-16s null/blank=%d  class=%s\n", c1, sum(n), paste(class(v), collapse = "/")))
}
cat("finals labels remaining:", sum(out$Round %in% FINALS), "\n")
nonascii <- grepl("[^\x01-\x7f]", paste(out$Player, out$Venue, out$Playing.for))
cat("rows containing non-ASCII text:", sum(nonascii), "\n")
if (any(nonascii)) print(unique(out$Player[nonascii]))

dir.create("data_history", showWarnings = FALSE)
write.csv(out, "data_history/brownlow_votes_1990_2006.csv",
          row.names = FALSE, fileEncoding = "UTF-8", na = "")
cat("\nwrote data_history/brownlow_votes_1990_2006.csv\n")
cat("DONE\n")
