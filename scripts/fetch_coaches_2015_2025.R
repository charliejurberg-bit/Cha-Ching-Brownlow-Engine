# Regenerate the 2015-2025 coaches vote archive from fitzRoy.
#
# Run from the repository root, not from inside scripts/:
#   Rscript scripts/fetch_coaches_2015_2025.R
#
# WHY THIS EXISTS
#
# coaches_votes_all.csv is a byte-exact concatenation of two halves:
# coaches_votes_2006_2014.csv (11,196 rows) written by fetch_extended_data.R,
# and coaches_votes_2015_2025.csv (14,955 rows) written by nothing in this
# repository. The later half carries every known defect in the archive:
# 106 fractional vote values, 81 duplicate Season+Round+player+club groups,
# and four recurring phantom fixtures. The earlier half has none.
#
# scripts/validate_coaches.py detects those defects. This script is the missing
# regeneration path, so the later half can be rebuilt from source and compared
# against what is currently checked in.
#
# WHAT THIS SCRIPT DOES NOT DO
#
# It writes ONE file, data_history/coaches_votes_2015_2025_regen.csv, and never
# touches coaches_votes_2015_2025.csv or coaches_votes_all.csv. Merging,
# replacing and any change to the model readers are separate decisions and are
# deliberately not made here.
#
# THE ONE DELIBERATE DIFFERENCE FROM fetch_extended_data.R
#
# The parent script catches a failed season, prints "ERROR (skipping)", and
# carries on to write whatever it did collect:
#
#     }, error = function(e) {
#       cat(sprintf("ERROR (skipping): %s\n", e$message))
#     })
#     ...
#     if (length(cv_list) > 0) { write.csv(...) }
#
# A season that errors therefore produces a SHORT FILE that looks complete.
# Nothing downstream can tell the difference, because the output carries no
# record of which seasons were asked for. This script inverts that: any season
# that errors or returns zero rows aborts the run and NOTHING is written. A
# partial file is worse than no file, because a partial file gets used.
#
# That inversion was originally motivated by a hypothesis that a skipped season
# explained the defects in the 2015-2025 half. THE FIRST RUN OF THIS SCRIPT
# DISPROVED IT. All 11 seasons returned rows, and the output was row-for-row
# identical to the checked-in coaches_votes_2015_2025.csv, 14,955 rows, every
# season matching exactly, with the same 81 duplicate groups and the same 106
# fractional values. The defects are in what fitzRoy returns, not in how the
# file was written. The strict handling stays because it is the right default,
# not because it caught anything here.
#
# EXIT CODE
# 0 only if all 11 seasons returned rows and the file was written. 1 on any
# errored season, any empty season, an unexpected column schema, or a failed
# write. Non-zero always means no file was written, or the existing one was
# left exactly as it was.

suppressMessages(library(fitzRoy))

LO <- 2015
HI <- 2025
OUT <- "data_history/coaches_votes_2015_2025_regen.csv"

# The schema the existing halves carry, and what the model readers parse.
# brownlow_model.py splits Player.Name on the parenthetical to get CV_Player and
# CV_Team, so a change in these names or their order is a breaking change and
# the run stops rather than writing a file the readers cannot key.
EXPECTED_COLS <- c("Season", "Round", "Home.Team", "Away.Team",
                   "Player.Name", "Coaches.Votes")

die <- function(...) {
  cat("\n", sprintf(...), "\n", sep = "")
  cat("ABORTED. Nothing was written. ", OUT, " is unchanged.\n", sep = "")
  quit(save = "no", status = 1)
}

if (!dir.exists("data_history")) {
  die("data_history/ not found. Run this from the repository root.")
}

cat("=== Regenerating coaches votes ", LO, "-", HI, " ===\n", sep = "")
cat("Source: fitzRoy fetch_coaches_votes(comp = \"AFLM\")\n")
cat("Target: ", OUT, "\n\n", sep = "")

cv_list <- list()
failures <- character(0)
counts <- integer(0)

for (yr in LO:HI) {
  cat(sprintf("  %d ... ", yr))
  # The result is assigned out of tryCatch rather than inside the handler,
  # because an error handler that only prints leaves the loop variable holding
  # the previous season's value. That is the shape of a broadcast bug.
  cv <- tryCatch(
    fetch_coaches_votes(season = yr, comp = "AFLM"),
    error = function(e) {
      cat(sprintf("ERROR: %s\n", conditionMessage(e)))
      failures <<- c(failures, sprintf("%d (error: %s)", yr, conditionMessage(e)))
      NULL
    }
  )
  if (is.null(cv)) {
    next
  }
  if (nrow(cv) == 0) {
    cat("EMPTY (0 rows)\n")
    failures <- c(failures, sprintf("%d (empty: 0 rows returned)", yr))
    next
  }
  cv$Season <- yr  # the feed does not always carry it; the readers require it
  cv_list[[as.character(yr)]] <- cv
  counts[as.character(yr)] <- nrow(cv)
  cat(sprintf("OK (%d rows)\n", nrow(cv)))
}

if (length(failures) > 0) {
  die("%d of %d season(s) did not return usable data:\n  %s",
      length(failures), HI - LO + 1, paste(failures, collapse = "\n  "))
}

if (length(cv_list) != (HI - LO + 1)) {
  die("collected %d season(s), expected %d. Refusing to write a short file.",
      length(cv_list), HI - LO + 1)
}

out <- do.call(rbind, cv_list)
rownames(out) <- NULL

missing <- setdiff(EXPECTED_COLS, names(out))
if (length(missing) > 0) {
  die("feed is missing expected column(s): %s\n  got: %s",
      paste(missing, collapse = ", "), paste(names(out), collapse = ", "))
}
# Column ORDER is normalised rather than asserted, so a feed that returns the
# same fields rearranged still produces a file diffable against the existing
# one. Extra columns are dropped, and named, so the drop is never silent.
extra <- setdiff(names(out), EXPECTED_COLS)
if (length(extra) > 0) {
  cat("\n  note: dropping ", length(extra), " column(s) not in the existing ",
      "schema: ", paste(extra, collapse = ", "), "\n", sep = "")
}
out <- out[, EXPECTED_COLS]

cat("\nPer-season row counts:\n")
for (yr in LO:HI) {
  cat(sprintf("  %d  %6d\n", yr, counts[as.character(yr)]))
}
cat(sprintf("  %s  %6d\n", "TOTAL", nrow(out)))

write.csv(out, OUT, row.names = FALSE, na = "")
if (!file.exists(OUT)) {
  die("write.csv reported no error but %s does not exist.", OUT)
}

cat("\nWrote ", OUT, " (", nrow(out), " rows, ", ncol(out), " columns)\n", sep = "")
cat("Nothing else was modified. Next:\n")
cat("  python scripts/validate_coaches.py --coaches ", OUT, "\n", sep = "")
quit(save = "no", status = 0)
