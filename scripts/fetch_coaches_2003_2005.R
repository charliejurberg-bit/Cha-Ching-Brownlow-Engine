# fetch_coaches_2003_2005.R
#
# The three seasons the coaches-vote archive was missing.
#
#   Rscript scripts/fetch_coaches_2003_2005.R
#
# WHY THIS EXISTS AS ITS OWN SCRIPT
# The AFLCA award began in 2003, but fetch_extended_data.R hardcodes
# `for (yr in 2006:2014)`, so 2003, 2004 and 2005 were never pulled. That is a
# fetch-range choice, not a source limitation, and it made every "all time"
# coaches-vote claim quietly wrong: four of the top sixteen career vote-getters
# were active across those three seasons with none of it counted.
#
# It is separate from fetch_extended_data.R on purpose. That script also
# re-fetches 2007-2014 player stats and rewrites two large tracked files, none
# of which needs to happen to add three seasons of votes. This one writes ONE
# new file and touches nothing else.
#
# It cannot disturb data_2026/coaches_votes_2026.csv, which holds the
# hand-transcribed rounds 24 and 25 that a refetch would silently delete. That
# file is written only by data_2026/fetch_coaches.R and is not referenced here.

library(fitzRoy)

OUT <- "data_history/coaches_votes_2003_2005.csv"
YEARS <- 2003:2005

if (file.exists(OUT)) {
  stop(sprintf("%s already exists. Delete it first if you mean to refetch.", OUT))
}

cat("=== Fetching coaches votes 2003-2005 ===\n")
cv_list <- list()
for (yr in YEARS) {
  cat(sprintf("  %d ... ", yr))
  tryCatch({
    cv <- fetch_coaches_votes(season = yr, comp = "AFLM")
    if (!is.null(cv) && nrow(cv) > 0) {
      cv_list[[as.character(yr)]] <- cv
      cat(sprintf("OK (%d rows, %d votes)\n", nrow(cv), sum(cv$Coaches.Votes)))
    } else {
      cat("no data returned\n")
    }
  }, error = function(e) {
    cat(sprintf("ERROR (skipping): %s\n", e$message))
  })
}

if (length(cv_list) == 0) {
  stop("No coaches votes retrieved for 2003-2005. Nothing written.")
}

cv_out <- do.call(rbind, cv_list)
dir.create("data_history", showWarnings = FALSE)
write.csv(cv_out, OUT, row.names = FALSE)
cat(sprintf("\nSaved %d rows -> %s\n", nrow(cv_out), OUT))
cat("Seasons retrieved:", paste(sort(unique(cv_out$Season)), collapse = ", "), "\n")
cat("\nNow run: python scripts/rebuild_coaches_all.py\n")
