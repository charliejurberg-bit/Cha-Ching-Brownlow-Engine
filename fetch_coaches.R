# AFLCA coaches votes for one season, via fitzRoy, GUARDED.
#
#     Rscript fetch_coaches.R 2027                 # writes data_2027/coaches_votes_2027.csv
#     Rscript fetch_coaches.R 2027 some/other.csv  # write elsewhere (for testing)
#     Rscript fetch_coaches.R 2027 - --force       # overwrite despite the guard
#
# Replaces data_2026/fetch_coaches.R, whose write.csv was unconditional. In 2026
# fitzRoy's feed stopped at raw round 23 while rounds 24 and 25 were transcribed
# by hand, so a refetch would have silently deleted two rounds and dropped the
# model's routing from 207/0 to 189/18 (CLAUDE.md, "Update chain").
#
# The guard: when a file already exists, the fetch is written only if EVERY game
# (round + home + away) in that file is still in the fetch. A row count or a
# last-round check is not enough, and that was measured, not assumed: on 27
# September 2026 the feed returned 1,380 rows through "round 29" against the
# file's 1,346 through round 25, so it passed both, yet its rounds 24-29 were the
# FINALS mislabelled, 12 rows each, and writing it would have deleted the 110
# hand-transcribed home-and-away rows of rounds 24 and 25. It also refuses an
# empty fetch.

suppressMessages(library(fitzRoy))
args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) stop("usage: Rscript fetch_coaches.R <season> [out.csv|-] [--force]")
season <- as.integer(args[1])
out <- if (length(args) >= 2 && args[2] != "-") args[2] else
  sprintf("data_%d/coaches_votes_%d.csv", season, season)
force <- "--force" %in% args
dir.create(dirname(out), showWarnings = FALSE, recursive = TRUE)

coaches <- fetch_coaches_votes(season = season, comp = "AFLM")
if (is.null(coaches) || nrow(coaches) == 0) {
  cat("No coaches votes fetched; nothing written.\n")
  quit(status = 1)
}
new_max <- max(suppressWarnings(as.numeric(coaches$Round)), na.rm = TRUE)
cat(sprintf("Fetched %d rows through round %s\n", nrow(coaches), new_max))

if (file.exists(out) && !force) {
  old <- read.csv(out, check.names = FALSE)
  game_key <- function(d) unique(paste(d$Round, d[["Home.Team"]], d[["Away.Team"]], sep = " | "))
  lost <- setdiff(game_key(old), game_key(coaches))
  if (length(lost) > 0) {
    cat(sprintf(paste0("REFUSED: %d game(s) in %s are missing from the fetch, e.g. %s. ",
                       "Keeping the file on disk. Pass --force only if the file is known ",
                       "to be wrong.\n"),
                length(lost), out, paste(head(lost, 3), collapse = "; ")))
    quit(status = 1)
  }
}
write.csv(coaches, out, row.names = FALSE)
cat(sprintf("Done - saved to %s\n", out))
