
# fetch_extended_data.R
# Pulls 2007-2014 player stats and 2006-2014 coaches votes from AFL Tables via fitzRoy.
# Same functions used for the existing 2015-2025 data — output format is identical.
#
# Run in RGui or RStudio:
#   source("fetch_extended_data.R")
#
# Then run:
#   python merge_extended_data.py

library(fitzRoy)

# ── Player stats 2007–2014 ────────────────────────────────────
cat("=== Fetching player stats 2007-2014 from AFL Tables ===\n")
stats_list <- list()

for (yr in 2007:2014) {
  cat(sprintf("  %d ... ", yr))
  tryCatch({
    s <- fetch_player_stats_afltables(season = yr)
    if (!is.null(s) && nrow(s) > 0) {
      stats_list[[as.character(yr)]] <- s
      cat(sprintf("OK (%d rows)\n", nrow(s)))
    } else {
      cat("no data returned\n")
    }
  }, error = function(e) {
    cat(sprintf("ERROR: %s\n", e$message))
  })
}

if (length(stats_list) > 0) {
  stats_out <- do.call(rbind, stats_list)
  write.csv(stats_out, "fitzroy_stats_2007_2014.csv", row.names = FALSE)
  cat(sprintf("\nSaved %d rows -> fitzroy_stats_2007_2014.csv\n", nrow(stats_out)))
} else {
  cat("No stats data retrieved.\n")
}

# ── Coaches votes 2006–2014 ───────────────────────────────────
cat("\n=== Fetching coaches votes 2006-2014 ===\n")
cv_list <- list()

for (yr in 2006:2014) {
  cat(sprintf("  %d ... ", yr))
  tryCatch({
    cv <- fetch_coaches_votes(season = yr, comp = "AFLM")
    if (!is.null(cv) && nrow(cv) > 0) {
      cv_list[[as.character(yr)]] <- cv
      cat(sprintf("OK (%d rows)\n", nrow(cv)))
    } else {
      cat("no data returned\n")
    }
  }, error = function(e) {
    cat(sprintf("ERROR (skipping): %s\n", e$message))
  })
}

if (length(cv_list) > 0) {
  cv_out <- do.call(rbind, cv_list)
  write.csv(cv_out, "coaches_votes_2006_2014.csv", row.names = FALSE)
  cat(sprintf("\nSaved %d rows -> coaches_votes_2006_2014.csv\n", nrow(cv_out)))
} else {
  cat("No coaches votes data retrieved.\n")
}

cat("\nDone. Run: python merge_extended_data.py\n")
