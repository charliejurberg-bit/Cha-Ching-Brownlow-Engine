
library(fitzRoy)
cat('Fetching 2026 player stats from AFLTables...
')
stats <- fetch_player_stats_afltables(season = 2026)
cat(paste('Rows fetched:', nrow(stats), '
'))
cat(paste('Max round:', max(as.numeric(stats$Round[!is.na(as.numeric(stats$Round))]), na.rm=TRUE), '
'))
write.csv(stats, 'data_2026/afltables_2026.csv', row.names = FALSE)
cat('Done - saved to data_2026/afltables_2026.csv
')
