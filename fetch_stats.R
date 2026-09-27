# AFLTables player stats for one season, via fitzRoy.
#
#     Rscript fetch_stats.R 2027                 # writes data_2027/afltables_2027.csv
#     Rscript fetch_stats.R 2026 some/other.csv  # write elsewhere (for testing)
#
# update.py passes season.LIVE_SEASON. Replaces data_2026/fetch_stats_2026.R,
# which had the season written into it.
#
# Refuses to write an empty fetch: AFLTables before Opening Round, or a fitzRoy
# failure that returns zero rows, would otherwise blank the season's file.

suppressMessages(library(fitzRoy))
args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) stop("usage: Rscript fetch_stats.R <season> [out.csv]")
season <- as.integer(args[1])
out <- if (length(args) >= 2) args[2] else sprintf("data_%d/afltables_%d.csv", season, season)
dir.create(dirname(out), showWarnings = FALSE, recursive = TRUE)

cat(sprintf("Fetching %d player stats from AFLTables...\n", season))
stats <- fetch_player_stats_afltables(season = season)
if (is.null(stats) || nrow(stats) == 0) {
  cat("No rows fetched; nothing written.\n")
  quit(status = 1)
}
rounds <- suppressWarnings(as.numeric(stats$Round))
cat(sprintf("Rows fetched: %d\n", nrow(stats)))
cat(sprintf("Max round: %s\n", max(rounds, na.rm = TRUE)))
write.csv(stats, out, row.names = FALSE)
cat(sprintf("Done - saved to %s\n", out))
