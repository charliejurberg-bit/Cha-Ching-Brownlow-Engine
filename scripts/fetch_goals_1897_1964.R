# Per-player, per-game goals for 1897-1964, the years before
# data_history/fitzroy_stats_1965_2006.csv.gz starts.
#
# Run from the repository root:
#   Rscript scripts/fetch_goals_1897_1964.R
#
# Why: the single-game goals record (Fred Fanning, 18 in 1947) and most of
# the all-time goals ladder sit before 1965, so a record book built on the
# 1965-on archive alone would claim "all time" for a window that misses them.
# Goals and behinds are the only per-player stats AFLTables carries this far
# back, plus age and career game number (the desk's age and game brackets);
# everything else stays 1965 on. Finals included, like the 1965-on file.
# Read by desk/record_book.py.

suppressMessages(library(fitzRoy))

KEEP <- c("Season", "Round", "Date", "Venue", "ID", "Player", "First.name",
          "Surname", "Playing.for", "Home.team", "Away.team", "Goals", "Behinds",
          "Age", "Career.Games")

parts <- list()
for (yr in 1897:1964) {
  d <- tryCatch(suppressMessages(as.data.frame(fetch_player_stats_afltables(season = yr))),
                error = function(e) { cat(yr, "FAILED:", conditionMessage(e), "\n"); NULL })
  if (is.null(d) || nrow(d) == 0) stop(sprintf("no rows for %d; refusing to write a partial file", yr))
  have <- intersect(KEEP, names(d))
  d <- d[, have]
  if (!"Player" %in% have) d$Player <- paste(d$First.name, d$Surname)
  parts[[as.character(yr)]] <- d[, intersect(KEEP, names(d))]
  cat(sprintf("%d: %d rows, %d goals\n", yr, nrow(d), sum(d$Goals, na.rm = TRUE)))
}

out <- do.call(rbind, parts)
rownames(out) <- NULL
cat("rows:", nrow(out), "\n")
write.csv(out, gzfile("data_history/goals_1897_1964.csv.gz"), row.names = FALSE,
          fileEncoding = "UTF-8", na = "")
cat("wrote data_history/goals_1897_1964.csv.gz\nDONE\n")
