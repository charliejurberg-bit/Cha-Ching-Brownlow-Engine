# AFLW player stats per match, from the AFL API via fitzRoy.
#
#   Rscript aflw/fetch_stats.R [season ...]      default: 2017 to the current year
#
# Writes data_aflw/stats_<season>.csv, one row per player per match. Keyed on the
# AFL's own ids (providerId for the match, player.playerId for the player), the
# same ids the vote feed uses, so votes join exactly with no name matching.
# 2022 held two AFLW seasons (6 and 7); fitzRoy returns both under 2022 and the
# compSeason id tells them apart, so it is written as its own column.
suppressMessages(library(fitzRoy))
args <- commandArgs(trailingOnly = TRUE)
seasons <- if (length(args)) as.integer(args) else 2017:as.integer(format(Sys.Date(), "%Y"))
dir.create("data_aflw", showWarnings = FALSE)
for (s in seasons) {
  x <- tryCatch(fetch_player_stats(s, comp = "AFLW", source = "AFL"),
                error = function(e) { message(s, ": ", conditionMessage(e)); NULL })
  if (is.null(x) || !nrow(x)) { message(s, ": nothing"); next }
  x <- as.data.frame(x)
  keep <- vapply(x, function(col) !is.list(col), logical(1))
  x <- x[, keep]
  out <- file.path("data_aflw", sprintf("stats_%d.csv", s))
  write.csv(x, out, row.names = FALSE)
  message(s, ": ", nrow(x), " rows, ", length(unique(x$providerId)), " matches -> ", out)
}
