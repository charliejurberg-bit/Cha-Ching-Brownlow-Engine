# AFLW coaches votes (AFLCA champion player), per match, via fitzRoy.
#
#   Rscript aflw/fetch_coaches.R [season ...]      default: 2017 to the current year
#
# Writes data_aflw/coaches_<season>.csv. The feed carries names, clubs and
# rounds but no player ids, so it joins to the stats by name within team and
# round (aflw/build.py), not by id. Each match should total 30 (5-4-3-2-1 from
# each of two coaches); build.py reports any that do not.
suppressMessages(library(fitzRoy))
args <- commandArgs(trailingOnly = TRUE)
seasons <- if (length(args)) as.integer(args) else 2017:as.integer(format(Sys.Date(), "%Y"))
for (s in seasons) {
  x <- tryCatch(fetch_coaches_votes(season = s, comp = "AFLW"),
                error = function(e) { message(s, ": ", conditionMessage(e)); NULL })
  if (is.null(x) || !nrow(x)) { message(s, ": nothing"); next }
  out <- file.path("data_aflw", sprintf("coaches_%d.csv", s))
  write.csv(as.data.frame(x), out, row.names = FALSE)
  message(s, ": ", nrow(x), " rows -> ", out)
}
