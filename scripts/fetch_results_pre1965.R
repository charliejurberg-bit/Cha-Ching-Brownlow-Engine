# Build data_history/match_results_1897_1965.csv
#
# Run from the repository root, not from inside scripts/:
#   Rscript scripts/fetch_results_pre1965.R
#
# The pre-1965 tier for team_h2h.py. team_h2h_spec.md section 2 rules out
# `_tmp/match_results_all.csv` on the grounds that it was produced by a script
# that no longer exists and has no tracked regeneration path. This file IS that
# regeneration path, which is the condition the spec set for adopting a
# match-level source.
#
# Source is fetch_results_afltables(), a MATCH-level feed. It is not the feed
# the 1965+ tier uses. It reaches back to 1897 because it carries no player
# statistics, and it carries no player statistics because none were recorded.
# The same trade costs it two fields the main tier has:
#
#   - no Local.start.time  -> no timeslot bins pre-1965
#   - no quarter scores    -> no quarter records and no quarter streak bases
#
# Both absences are structural in the source, not a fetch option, and the
# loader refuses to invent either.
#
# 1965 is fetched deliberately even though the main tier already covers it. It
# is the overlap season and exists so team_match_table_pre1965.validate_join()
# can check the two feeds agree on a season they both hold. Without an overlap
# the tier join is unverifiable. The loader drops it from the tier itself.
#
# Output: closed range 1897-1965, UTF-8 no BOM, na = "".

suppressMessages(library(fitzRoy))

LO <- 1897
HI <- 1965  # 1964 is the tier; 1965 is the overlap-validation season

KEEP <- c("Season", "Round", "Round.Type", "Round.Number", "Date", "Venue",
          "Home.Team", "Home.Goals", "Home.Behinds", "Home.Points",
          "Away.Team", "Away.Goals", "Away.Behinds", "Away.Points", "Margin")

parts <- list()
for (yr in LO:HI) {
  d <- suppressMessages(as.data.frame(fetch_results_afltables(season = yr)))
  missing <- setdiff(KEEP, names(d))
  if (length(missing) > 0) {
    stop(sprintf("%d: source is missing columns: %s", yr,
                 paste(missing, collapse = ", ")))
  }
  d <- d[, KEEP]
  parts[[as.character(yr)]] <- d
  cat(sprintf("%d: %d matches (%s)\n", yr, nrow(d),
              paste(sort(unique(d$Round.Type)), collapse = "/")))
}

out <- do.call(rbind, parts)
rownames(out) <- NULL

cat("\n--- pre-write checks ---\n")
cat("rows:", nrow(out), " cols:", ncol(out), "\n")
cat("seasons:", min(out$Season), "to", max(out$Season), "\n")
cat("round types:", paste(sort(unique(out$Round.Type)), collapse = ", "), "\n")
cat("finals round labels:",
    paste(sort(unique(out$Round[out$Round.Type != "Regular"])), collapse = ", "),
    "\n")
for (c1 in KEEP) {
  v <- out[[c1]]
  n <- is.na(v)
  if (is.character(v)) n <- n | trimws(v) == ""
  cat(sprintf("  %-14s null/blank=%d  class=%s\n", c1, sum(n),
              paste(class(v), collapse = "/")))
}

# The points identity, asserted here rather than assumed, mirroring assertion 6
# in team_match_table.py.
bad <- sum(out$Home.Points != out$Home.Goals * 6 + out$Home.Behinds) +
       sum(out$Away.Points != out$Away.Goals * 6 + out$Away.Behinds)
cat("rows where Points != Goals*6 + Behinds:", bad, "\n")
if (bad > 0) stop("points identity failed; do not write")

cat("clubs:", paste(sort(unique(c(out$Home.Team, out$Away.Team))),
                    collapse = ", "), "\n")

dir.create("data_history", showWarnings = FALSE)
write.csv(out, "data_history/match_results_1897_1965.csv",
          row.names = FALSE, fileEncoding = "UTF-8", na = "")
cat("\nwrote data_history/match_results_1897_1965.csv\n")
cat("DONE\n")
