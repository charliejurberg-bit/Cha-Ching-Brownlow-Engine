
library(fitzRoy)
coaches <- fetch_coaches_votes(season = 2026, comp = "AFLM")
write.csv(coaches, "data_2026/coaches_votes_2026.csv", row.names = FALSE)
cat("Done\n")
