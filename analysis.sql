SELECT
    species,
    island,
    COUNT(*) AS total_penguins,
    ROUND(AVG(body_mass_g), 2) AS mean_weight
FROM data
WHERE sex IS NOT NULL
GROUP BY species, island
ORDER BY mean_weight DESC;