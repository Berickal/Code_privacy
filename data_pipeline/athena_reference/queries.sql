-- Reference SWH Athena queries (report §6.4). Not used in the no-AWS build.
-- Canonical DDL: https://docs.softwareheritage.org/devel/swh-export/graph/athena.html

-- Q1: post-cutoff date verification
SELECT de.target AS sha1_git, MIN(r.committer_date) AS first_committed
FROM directory_entry de
JOIN revision r ON r.directory = de.directory_id
WHERE de.type = 'file' AND de.target IN (<candidate_sha1_git_list>)
GROUP BY de.target
HAVING MIN(r.committer_date) > TIMESTAMP '2023-11-01';

-- Q2: SPDX license lookup (join against the SWH License Dataset)
-- Q3: content-hash clone dedup
SELECT target AS sha1_git, COUNT(DISTINCT directory_id) AS copy_count
FROM directory_entry
WHERE type = 'file' AND target IN (<candidate_sha1_git_list>)
GROUP BY target
HAVING COUNT(DISTINCT directory_id) > 1;

-- Q4: GitHub origin URL per file (attribution ground truth)
