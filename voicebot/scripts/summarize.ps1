$d = Get-Content voicebot\data\issues.json -Raw | ConvertFrom-Json
"=== TOTALS ==="
"total: $($d.Count)"
"no_user: $(($d | Where-Object { $_.skipped_reason -eq 'no_user_turns' }).Count)"
"llm-analyzed: $(($d | Where-Object { $_.skipped_reason -ne 'no_user_turns' }).Count)"
""
"=== QUALITY (analyzed only) ==="
$d | Where-Object { $_.skipped_reason -ne 'no_user_turns' } | Group-Object overall_quality | Sort-Object Count -Descending | ForEach-Object { "  $($_.Name): $($_.Count)" }
""
"=== ISSUE CATEGORIES ==="
$cats = @{}
foreach ($call in $d) {
  if ($call.issues) {
    foreach ($iss in $call.issues) {
      $c = $iss.category
      if (-not $cats.ContainsKey($c)) { $cats[$c] = 0 }
      $cats[$c]++
    }
  }
}
$cats.GetEnumerator() | Sort-Object Value -Descending | ForEach-Object { "  $($_.Key): $($_.Value)" }
""
$withIssues = ($d | Where-Object { $_.issues -and $_.issues.Count -gt 0 }).Count
"calls with >=1 issue: $withIssues"
